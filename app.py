from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
import os
from datetime import datetime, timedelta
from models import db, User, Expense, Income, SavingsChallenge
from budgets import budgets
from analytics import analytics
from auth import auth
from expenses import expenses
from income import incomes
from savings import savings
from categories import categories, DEFAULT_EXPENSE_CATEGORIES, ExpenseCategory
from smart_budget import smart_budget
from recurring_transactions import recurring
from financial_goals import goals
from export_data import export_data
from export_data import export_csv


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

def get_monthly_date_ranges():
    """Helper function to get date ranges for monthly calculations"""
    today = datetime.utcnow()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = (start_of_month + timedelta(days=MONTH_END_DAY_ADJUSTMENT)).replace(day=1) - timedelta(seconds=1)
    return today, start_of_month, end_of_month

def get_recent_transactions(user_id):
    """Get recent expenses and incomes"""
    try:
        expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).limit(5).all()
        incomes = Income.query.filter_by(user_id=user_id).order_by(Income.date.desc()).limit(5).all()
        return expenses, incomes
    except Exception as e:
        app.logger.error(f"Error fetching transactions: {str(e)}")
        return [], []

def calculate_financial_metrics(user_id, start_of_month, end_of_month):
    """Calculate financial metrics"""
    try:
        # Monthly metrics
        monthly_expenses = db.session.query(db.func.sum(Expense.amount))\
            .filter(Expense.user_id == user_id,
                   Expense.date >= start_of_month,
                   Expense.date <= end_of_month).scalar() or 0
                   
        monthly_income = db.session.query(db.func.sum(Income.amount))\
            .filter(Income.user_id == user_id,
                   Income.date >= start_of_month,
                   Income.date <= end_of_month).scalar() or 0
        
        # Total balance
        total_expenses = db.session.query(db.func.sum(Expense.amount))\
            .filter_by(user_id=user_id).scalar() or 0
        total_incomes = db.session.query(db.func.sum(Income.amount))\
            .filter_by(user_id=user_id).scalar() or 0
        total_balance = total_incomes - total_expenses
        
        return {
            'monthly_expenses': monthly_expenses,
            'monthly_income': monthly_income,
            'total_balance': total_balance
        }
    except Exception as e:
        app.logger.error(f"Error calculating metrics: {str(e)}")
        return {
            'monthly_expenses': 0,
            'monthly_income': 0,
            'total_balance': 0
        }

# Constants for date calculations
CHART_MONTHS_RANGE = 180  # days
MONTH_END_DAY_ADJUSTMENT = 32  # days to add to find next month

def get_chart_data(user_id, start_date):
    """Get data for charts"""
    try:
        # Monthly expense data
        monthly_data = db.session.query(
            db.func.strftime('%Y-%m', Expense.date).label('month'),
            db.func.sum(Expense.amount).label('expenses')
        ).filter(
            Expense.user_id == user_id,
            Expense.date >= start_date
        ).group_by('month').all()
        
        # Monthly income data
        monthly_income_data = db.session.query(
            db.func.strftime('%Y-%m', Income.date).label('month'),
            db.func.sum(Income.amount).label('income')
        ).filter(
            Income.user_id == user_id,
            Income.date >= start_date
        ).group_by('month').all()
        
        return {
            'months': [item[0] for item in monthly_data],
            'expense_data': [float(item[1]) for item in monthly_data],
            'income_data': [float(item[1]) for item in monthly_income_data]
        }
    except Exception as e:
        app.logger.error(f"Error getting chart data: {str(e)}")
        return {
            'months': [],
            'expense_data': [],
            'income_data': []
        }

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        today, start_of_month, end_of_month = get_monthly_date_ranges()
        start_date = today - timedelta(days=CHART_MONTHS_RANGE)
        
        # Get data
        expenses, incomes = get_recent_transactions(current_user.id)
        savings_challenges = SavingsChallenge.query.filter_by(
            user_id=current_user.id, 
            completed=False
        ).all()
        
        metrics = calculate_financial_metrics(
            current_user.id, 
            start_of_month, 
            end_of_month
        )
        
        chart_data = get_chart_data(current_user.id, start_date)
        
        # Calculate savings streak
        savings_streak = 0
        if savings_challenges:
            most_recent = max(
                (c for c in savings_challenges if c.last_contribution_date),
                key=lambda x: x.last_contribution_date,
                default=None
            )
            savings_streak = most_recent.streak_days if most_recent else 0
        
        # Budget utilization
        budget_utilization = round(
            (metrics['monthly_expenses'] / metrics['monthly_income'] * 100) 
            if metrics['monthly_income'] > 0 else 0
        )
        
        # Savings tips
        savings_goal_message = (
            "You're on track with your savings!" 
            if metrics['monthly_income'] > metrics['monthly_expenses'] 
            else "Try to reduce expenses to meet your savings goal"
        )
        
        return render_template('dashboard.html', 
            expenses=expenses,
            incomes=incomes,
            savings_challenges=savings_challenges,
            total_balance=metrics['total_balance'],
            monthly_income=metrics['monthly_income'],
            monthly_expenses=metrics['monthly_expenses'],
            savings_streak=savings_streak,
            months=chart_data['months'],
            monthly_income_data=chart_data['income_data'],
            monthly_expense_data=chart_data['expense_data'],
            budget_utilization=budget_utilization,
            savings_goal_message=savings_goal_message,
            smart_saving_tip="Consider setting up automatic transfers to your savings account"
        )
        
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        flash("An error occurred while loading the dashboard", "error")
        return redirect(url_for('index'))

app.register_blueprint(budgets, url_prefix='/budget')
app.register_blueprint(analytics, url_prefix='/analytics')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(expenses, url_prefix='/expense')
app.register_blueprint(incomes, url_prefix='/income')
app.register_blueprint(savings, url_prefix='/savings')
app.register_blueprint(categories, url_prefix='/categories')
app.register_blueprint(smart_budget, url_prefix='/smart-budget')
app.register_blueprint(recurring, url_prefix='/recurring')
app.register_blueprint(goals, url_prefix='/goals')
app.register_blueprint(export_data, url_prefix='/export')

# Initialize default categories for new users
def init_default_categories(user_id):
    for cat in DEFAULT_EXPENSE_CATEGORIES:
        category = ExpenseCategory(
            name=cat['name'],
            description=cat['description'],
            is_default=True,
            user_id=user_id
        )
        db.session.add(category)
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)

# WSGI entry point
def create_app():
    with app.app_context():
        db.create_all()
    return app


app.add_url_rule('/export/csv', 'export_csv', export_csv)