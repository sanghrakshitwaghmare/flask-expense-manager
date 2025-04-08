from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from enum import Enum

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    expenses = db.relationship('Expense', backref='user', lazy=True)
    expense_categories = db.relationship('ExpenseCategory', backref='user', lazy=True)
    incomes = db.relationship('Income', backref='user', lazy=True)
    budgets = db.relationship('Budget', backref='user', lazy=True)
    savings_challenges = db.relationship('SavingsChallenge', backref='user', lazy=True)
    recurring_expenses = db.relationship('RecurringExpense', backref='user', lazy=True)
    expense_streaks = db.relationship('ExpenseStreak', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ExpenseCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    is_default = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expenses = db.relationship('Expense', backref='category_info', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class BudgetPeriod(Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    period = db.Column(db.Enum(BudgetPeriod), nullable=False, default=BudgetPeriod.MONTHLY)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    alerts_enabled = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alerts = db.relationship('BudgetAlert', backref='budget', lazy=True)

    def get_usage_percentage(self):
        try:
            end_date = datetime.utcnow()
            if self.period == BudgetPeriod.DAILY:
                start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            elif self.period == BudgetPeriod.WEEKLY:
                start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
                start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # MONTHLY
                start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get category ID safely
            category = ExpenseCategory.query.filter_by(name=self.category, user_id=self.user_id).first()
            if not category:
                return 0
            
            # Use SQLAlchemy aggregation for better performance
            total_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == self.user_id,
                Expense.category_id == category.id,
                Expense.date.between(start, end_date)
            ).scalar() or 0
            
            return (total_expenses / self.amount) * 100 if self.amount > 0 else 0
        except Exception as e:
            # Log the error and return a safe default
            print(f"Error calculating budget usage: {str(e)}")
            return 0

    def get_remaining_income(self):
        """Calculate remaining income after expenses for the current period"""
        end_date = datetime.utcnow()
        if self.period == BudgetPeriod.DAILY:
            start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == BudgetPeriod.WEEKLY:
            start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # MONTHLY
            start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_income = sum(income.amount for income in Income.query.filter(
            Income.user_id == self.user_id,
            Income.date.between(start, end_date)
        ).all())

        total_expenses = sum(expense.amount for expense in Expense.query.filter(
            Expense.user_id == self.user_id,
            Expense.date.between(start, end_date)
        ).all())

        return total_income - total_expenses

    def get_savings(self):
        """Calculate savings (remaining income minus budgeted amount)"""
        remaining_income = self.get_remaining_income()
        return remaining_income - self.amount if remaining_income > 0 else 0

class RecurringExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, yearly
    next_due_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class BudgetAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=False)
    threshold_percentage = db.Column(db.Float, nullable=False)  # 80 or 100
    triggered_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    acknowledged = db.Column(db.Boolean, default=False)

class ExpenseStreak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_tracked_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    streak_target = db.Column(db.Integer, default=7)  # Target days for streak

class SavingsChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200))
    completed = db.Column(db.Boolean, default=False)
    streak_days = db.Column(db.Integer, default=0)  # Track consecutive days of saving
    last_contribution_date = db.Column(db.DateTime)  # Track last contribution date
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def update_streak(self):
        if not self.last_contribution_date:
            self.streak_days = 1
        else:
            days_since_last = (datetime.utcnow() - self.last_contribution_date).days
            if days_since_last <= 1:  # Allow for same day or consecutive day contributions
                self.streak_days += 1
            else:
                self.streak_days = 1  # Reset streak if more than 1 day has passed
        self.last_contribution_date = datetime.utcnow()