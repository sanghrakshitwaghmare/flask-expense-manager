from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import db, Expense, Budget, BudgetPeriod, ExpenseCategory
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

smart_budget = Blueprint('smart_budget', __name__)

def calculate_average_spending(user_id, months_lookback=3):
    """Calculate average monthly spending by category"""
    start_date = datetime.utcnow() - timedelta(days=30 * months_lookback)
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= start_date
    ).all()
    
    category_totals = defaultdict(list)
    for expense in expenses:
        category = expense.category_info.name
        month = expense.date.strftime('%Y-%m')
        category_totals[(category, month)].append(expense.amount)
    
    category_averages = {}
    for (category, _), amounts in category_totals.items():
        if category not in category_averages:
            category_averages[category] = sum(amounts) / months_lookback
    
    return category_averages

def detect_spending_patterns(user_id):
    """Analyze spending patterns and trends"""
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
    patterns = defaultdict(lambda: {'total': 0, 'frequency': 0, 'avg_amount': 0})
    
    for expense in expenses:
        category = expense.category_info.name
        patterns[category]['total'] += expense.amount
        patterns[category]['frequency'] += 1
    
    for category in patterns:
        patterns[category]['avg_amount'] = (
            patterns[category]['total'] / patterns[category]['frequency']
            if patterns[category]['frequency'] > 0 else 0
        )
    
    return patterns

def generate_budget_recommendations(user_id):
    """Generate smart budget recommendations based on spending patterns"""
    avg_spending = calculate_average_spending(user_id)
    patterns = detect_spending_patterns(user_id)
    
    recommendations = {}
    for category, avg_amount in avg_spending.items():
        pattern = patterns.get(category, {})
        frequency = pattern.get('frequency', 0)
        
        # Apply smart rules for recommendations
        if frequency > 10:  # High frequency spending
            recommended = avg_amount * 1.1  # Add 10% buffer
        elif frequency > 5:  # Medium frequency
            recommended = avg_amount * 1.15  # Add 15% buffer
        else:  # Low frequency, might be irregular expenses
            recommended = avg_amount * 1.25  # Add 25% buffer
        
        recommendations[category] = round(recommended, 2)
    
    return recommendations

@smart_budget.route('/smart-budget/recommendations')
@login_required
def get_recommendations():
    recommendations = generate_budget_recommendations(current_user.id)
    current_budgets = {budget.category: budget.amount 
                      for budget in Budget.query.filter_by(user_id=current_user.id).all()}
    
    return render_template(
        'smart_budget/recommendations.html',
        recommendations=recommendations,
        current_budgets=current_budgets
    )

@smart_budget.route('/smart-budget/apply-recommendations', methods=['POST'])
@login_required
def apply_recommendations():
    selected_categories = request.form.getlist('categories')
    recommendations = generate_budget_recommendations(current_user.id)
    
    for category in selected_categories:
        # Update existing budget or create new one
        budget = Budget.query.filter_by(
            user_id=current_user.id,
            category=category
        ).first()
        
        if budget:
            budget.amount = recommendations[category]
        else:
            new_budget = Budget(
                category=category,
                amount=recommendations[category],
                period=BudgetPeriod.MONTHLY,
                user_id=current_user.id
            )
            db.session.add(new_budget)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Budget recommendations applied successfully!'})