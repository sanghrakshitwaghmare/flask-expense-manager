from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, SavingsChallenge
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange
from datetime import datetime, timedelta

goals = Blueprint('goals', __name__)

class FinancialGoalForm(FlaskForm):
    title = StringField('Goal Title', validators=[DataRequired(), Length(max=100)])
    target_amount = FloatField('Target Amount', validators=[
        DataRequired(),
        NumberRange(min=1, message='Target amount must be positive')
    ])
    end_date = DateField('Target Date', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=200)])

def calculate_milestone_rewards(current_amount, target_amount):
    """Calculate milestone rewards based on progress"""
    progress = (current_amount / target_amount) * 100 if target_amount > 0 else 0
    rewards = {
        25: 'Bronze Saver',
        50: 'Silver Stacker',
        75: 'Gold Accumulator',
        100: 'Platinum Master'
    }
    
    earned_rewards = []
    for threshold, reward in rewards.items():
        if progress >= threshold:
            earned_rewards.append({
                'name': reward,
                'threshold': threshold,
                'icon': f'medal_{reward.split()[0].lower()}'
            })
    
    return earned_rewards

def get_goal_statistics(goal):
    """Calculate various statistics for a financial goal"""
    now = datetime.utcnow()
    total_days = (goal.end_date - goal.start_date).days
    days_passed = (now - goal.start_date).days
    days_remaining = (goal.end_date - now).days
    
    progress = (goal.current_amount / goal.target_amount) * 100
    daily_target = (goal.target_amount - goal.current_amount) / days_remaining if days_remaining > 0 else 0
    
    return {
        'progress': round(progress, 1),
        'days_remaining': days_remaining,
        'daily_target': round(daily_target, 2),
        'streak_days': goal.streak_days,
        'rewards': calculate_milestone_rewards(goal.current_amount, goal.target_amount)
    }

@goals.route('/goals')
@login_required
def list_goals():
    active_goals = SavingsChallenge.query.filter_by(
        user_id=current_user.id,
        completed=False
    ).all()
    
    completed_goals = SavingsChallenge.query.filter_by(
        user_id=current_user.id,
        completed=True
    ).all()
    
    goals_stats = {}
    for goal in active_goals:
        goals_stats[goal.id] = get_goal_statistics(goal)
    
    return render_template(
        'goals/list.html',
        active_goals=active_goals,
        completed_goals=completed_goals,
        goals_stats=goals_stats
    )

@goals.route('/goals/add', methods=['GET', 'POST'])
@login_required
def add_goal():
    form = FinancialGoalForm()
    if form.validate_on_submit():
        if form.end_date.data <= datetime.utcnow().date():
            flash('Target date must be in the future', 'danger')
            return render_template('goals/form.html', form=form, title='Add Financial Goal')
        
        goal = SavingsChallenge(
            title=form.title.data,
            target_amount=form.target_amount.data,
            start_date=datetime.utcnow(),
            end_date=form.end_date.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(goal)
        db.session.commit()
        flash('Financial goal created successfully!', 'success')
        return redirect(url_for('goals.list_goals'))
    
    return render_template('goals/form.html', form=form, title='Add Financial Goal')

@goals.route('/goals/update-progress/<int:id>', methods=['POST'])
@login_required
def update_progress(id):
    goal = SavingsChallenge.query.get_or_404(id)
    if goal.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    amount = float(request.form.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    goal.current_amount += amount
    goal.update_streak()
    
    if goal.current_amount >= goal.target_amount:
        goal.completed = True
        flash('Congratulations! You\'ve achieved your financial goal!', 'success')
    
    db.session.commit()
    
    stats = get_goal_statistics(goal)
    return jsonify({
        'success': True,
        'current_amount': goal.current_amount,
        'stats': stats
    })

@goals.route('/goals/delete/<int:id>')
@login_required
def delete_goal(id):
    goal = SavingsChallenge.query.get_or_404(id)
    if goal.user_id != current_user.id:
        flash('You do not have permission to delete this goal.', 'danger')
        return redirect(url_for('goals.list_goals'))
    
    db.session.delete(goal)
    db.session.commit()
    flash('Financial goal deleted successfully!', 'success')
    return redirect(url_for('goals.list_goals'))