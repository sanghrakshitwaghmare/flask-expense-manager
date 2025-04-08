from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from collections import defaultdict
from models import db, Expense, Income, Budget

analytics = Blueprint('analytics', __name__)

@analytics.route('/analytics')
@login_required
def show_analytics():
    # Get date range for last 6 months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=180)
    
    # Monthly expense totals
    monthly_expenses = db.session.query(
        func.strftime('%Y-%m', Expense.date).label('month'),
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start_date
    ).group_by('month').all()
    
    # Category-wise totals
    category_expenses = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start_date
    ).group_by(Expense.category).all()
    
    # Calculate savings (income - expenses)
    total_income = db.session.query(func.sum(Income.amount)).\
        filter(Income.user_id == current_user.id,
               Income.date >= start_date).scalar() or 0
    
    total_expenses = db.session.query(func.sum(Expense.amount)).\
        filter(Expense.user_id == current_user.id,
               Expense.date >= start_date).scalar() or 0
    
    savings = total_income - total_expenses
    savings_rate = (savings / total_income * 100) if total_income > 0 else 0
    
    # Budget vs Actual Analysis
    budget_analysis = []
    budgets = current_user.budgets
    for budget in budgets:
        actual_spent = sum(expense.amount for expense in current_user.expenses
                         if expense.category == budget.category and
                         expense.date >= start_date)
        budget_analysis.append({
            'category': budget.category,
            'budget_amount': budget.amount,
            'actual_amount': actual_spent,
            'variance': budget.amount - actual_spent
        })
    
    return render_template('analytics/dashboard.html',
                          monthly_expenses=monthly_expenses,
                          category_expenses=category_expenses,
                          total_income=total_income,
                          total_expenses=total_expenses,
                          savings=savings,
                          savings_rate=savings_rate,
                          budget_analysis=budget_analysis)

@analytics.route('/api/monthly-trend')
@login_required
def monthly_trend():
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=180)
    
    monthly_data = db.session.query(
        func.strftime('%Y-%m', Expense.date).label('month'),
        func.sum(Expense.amount).label('expenses')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start_date
    ).group_by('month').all()
    
    return jsonify({
        'labels': [item[0] for item in monthly_data],
        'expenses': [float(item[1]) for item in monthly_data]
    })

@analytics.route('/api/category-distribution')
@login_required
def category_distribution():
    category_data = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == current_user.id
    ).group_by(Expense.category).all()
    
    return jsonify({
        'labels': [item[0] for item in category_data],
        'values': [float(item[1]) for item in category_data]
    })