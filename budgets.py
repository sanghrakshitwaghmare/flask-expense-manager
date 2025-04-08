from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length
from models import db, Budget, BudgetPeriod, BudgetAlert, Expense, ExpenseCategory
from datetime import datetime, timedelta
from sqlalchemy import func

budgets = Blueprint('budgets', __name__)

class BudgetForm(FlaskForm):
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    def __init__(self, *args, **kwargs):
        super(BudgetForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(c.id, c.name) for c in ExpenseCategory.query.filter_by(user_id=current_user.id).all()]
    amount = FloatField('Amount', validators=[DataRequired()])
    period = SelectField('Budget Period', choices=[(p.value, p.value.capitalize()) for p in BudgetPeriod], validators=[DataRequired()])
    alerts_enabled = BooleanField('Enable Budget Alerts')
    submit = SubmitField('Set Budget')

@budgets.route('/budgets')
@login_required
def list_budgets():
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    return render_template('budgets/list.html', budgets=budgets)

@budgets.route('/budgets/analytics')
@login_required
def budget_analytics():
    # Get all budgets for the user
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    
    # Calculate total budget amount, total spent, and remaining income
    total_budget_amount = sum(budget.amount for budget in budgets)
    total_spent = sum(budget.get_usage_percentage() * budget.amount / 100 for budget in budgets)
    total_remaining_income = sum(budget.get_remaining_income() for budget in budgets)
    total_savings = sum(budget.get_savings() for budget in budgets)
    
    # Calculate budget health (percentage of budgets under control)
    healthy_budgets = sum(1 for budget in budgets if budget.get_usage_percentage() <= 80)
    budget_health = (healthy_budgets / len(budgets) * 100) if budgets else 100
    
    # Get budget distribution data
    budget_categories = [budget.category for budget in budgets]
    budget_amounts = [budget.amount for budget in budgets]
    
    # Get spending trends data
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    dates = [(start_date + timedelta(days=x)).strftime('%Y-%m-%d') for x in range(31)]
    
    # Get daily spending data
    daily_spending = db.session.query(
        func.strftime('%Y-%m-%d', Expense.date).label('date'),
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date.between(start_date, end_date)
    ).group_by('date').all()
    
    # Create spending trend data
    spending_trend = [0] * 31
    for date, amount in daily_spending:
        day_index = (datetime.strptime(date, '%Y-%m-%d') - start_date).days
        if 0 <= day_index < 31:
            spending_trend[day_index] = float(amount)
    
    # Get budget trend (average daily budget)
    daily_budget = total_budget_amount / 30
    budget_trend = [daily_budget] * 31
    
    # Get unacknowledged budget alerts
    budget_alerts = BudgetAlert.query.join(Budget).filter(
        Budget.user_id == current_user.id,
        BudgetAlert.acknowledged == False
    ).order_by(BudgetAlert.triggered_date.desc()).all()
    
    return render_template('budgets/analytics.html',
                          total_budget_amount=total_budget_amount,
                          total_spent=total_spent,
                          total_remaining_income=total_remaining_income,
                          total_savings=total_savings,
                          budget_health=round(budget_health, 1),
                          budget_categories=budget_categories,
                          budget_amounts=budget_amounts,
                          spending_dates=dates,
                          spending_trend=spending_trend,
                          budget_trend=budget_trend,
                          budget_alerts=budget_alerts)

@budgets.route('/budgets/add', methods=['GET', 'POST'])
@login_required
def add_budget():
    form = BudgetForm()
    if form.validate_on_submit():
        category = ExpenseCategory.query.get(form.category_id.data)
        budget = Budget(
            category=category.name,
            amount=form.amount.data,
            period=BudgetPeriod(form.period.data),
            alerts_enabled=form.alerts_enabled.data,
            user_id=current_user.id
        )
        db.session.add(budget)
        db.session.commit()
        flash('Budget set successfully!', 'success')
        return redirect(url_for('budgets.list_budgets'))
    return render_template('budgets/form.html', form=form, title='Set Budget')

@budgets.route('/budgets/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_budget(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        flash('You do not have permission to edit this budget.', 'danger')
        return redirect(url_for('budgets.list_budgets'))
    
    form = BudgetForm(obj=budget)
    if form.validate_on_submit():
        category = ExpenseCategory.query.get(form.category_id.data)
        budget.category = category.name
        budget.amount = form.amount.data
        budget.period = BudgetPeriod(form.period.data)
        budget.alerts_enabled = form.alerts_enabled.data
        db.session.commit()
        flash('Budget updated successfully!', 'success')
        return redirect(url_for('budgets.list_budgets'))
    return render_template('budgets/form.html', form=form, title='Edit Budget')

@budgets.route('/budgets/delete/<int:id>')
@login_required
def delete_budget(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        flash('You do not have permission to delete this budget.', 'danger')
        return redirect(url_for('budgets.list_budgets'))
    
    db.session.delete(budget)
    db.session.commit()
    flash('Budget deleted successfully!', 'success')
    return redirect(url_for('budgets.list_budgets'))

@budgets.route('/api/budget-usage/<int:id>')
@login_required
def get_budget_usage(id):
    try:
        budget = Budget.query.get_or_404(id)
        if budget.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get category to ensure it exists
        category = ExpenseCategory.query.filter_by(name=budget.category, user_id=current_user.id).first()
        if not category:
            return jsonify({'error': f'Category {budget.category} not found'}), 404
        
        usage_percentage = budget.get_usage_percentage()
        
        # Check if we need to create alerts
        if budget.alerts_enabled:
            existing_alerts = BudgetAlert.query.filter_by(
                budget_id=budget.id,
                acknowledged=False
            ).order_by(BudgetAlert.threshold_percentage.desc()).all()
            
            # Only create new alerts if there are no unacknowledged alerts for higher thresholds
            highest_alert = existing_alerts[0].threshold_percentage if existing_alerts else 0
            
            if usage_percentage >= 100 and highest_alert < 100:
                alert = BudgetAlert(budget_id=budget.id, threshold_percentage=100)
                db.session.add(alert)
                flash(f'Warning: You have exceeded your {budget.category} budget!', 'danger')
            elif usage_percentage >= 80 and highest_alert < 80:
                alert = BudgetAlert(budget_id=budget.id, threshold_percentage=80)
                db.session.add(alert)
                flash(f'Warning: You have used 80% of your {budget.category} budget!', 'warning')
            
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error creating budget alert: {str(e)}")
        
        # Get remaining budget amount
        remaining_budget = budget.amount - (budget.amount * usage_percentage / 100)
        
        return jsonify({
            'usage_percentage': round(usage_percentage, 2),
            'period': budget.period.value,
            'remaining_budget': round(remaining_budget, 2),
            'category': budget.category,
            'alerts_enabled': budget.alerts_enabled
        })
    except Exception as e:
        print(f"Error in budget usage calculation: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@budgets.route('/api/acknowledge-alert/<int:alert_id>')
@login_required
def acknowledge_alert(alert_id):
    alert = BudgetAlert.query.get_or_404(alert_id)
    if alert.budget.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    alert.acknowledged = True
    db.session.commit()
    return jsonify({'status': 'success'})