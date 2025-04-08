from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, DateField, SubmitField
from wtforms.validators import DataRequired, Length
from datetime import datetime
from models import db, SavingsChallenge

savings = Blueprint('savings', __name__)

class SavingsChallengeForm(FlaskForm):
    title = StringField('Challenge Title', validators=[DataRequired(), Length(max=100)])
    target_amount = FloatField('Target Amount', validators=[DataRequired()])
    end_date = DateField('Target Date', validators=[DataRequired()])
    description = StringField('Description', validators=[Length(max=200)])
    submit = SubmitField('Create Challenge')

@savings.route('/savings')
@login_required
def list_challenges():
    challenges = SavingsChallenge.query.filter_by(user_id=current_user.id).all()
    return render_template('savings/list.html', challenges=challenges)

@savings.route('/savings/add', methods=['GET', 'POST'])
@login_required
def add_challenge():
    form = SavingsChallengeForm()
    if form.validate_on_submit():
        challenge = SavingsChallenge(
            title=form.title.data,
            target_amount=form.target_amount.data,
            current_amount=0,
            end_date=form.end_date.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(challenge)
        db.session.commit()
        flash('Savings Challenge created successfully!', 'success')
        return redirect(url_for('savings.list_challenges'))
    return render_template('savings/form.html', form=form, title='Create Savings Challenge')

@savings.route('/savings/update/<int:id>', methods=['POST'])
@login_required
def update_challenge(id):
    challenge = SavingsChallenge.query.get_or_404(id)
    if challenge.user_id != current_user.id:
        flash('You do not have permission to update this challenge.', 'danger')
        return redirect(url_for('savings.list_challenges'))
    
    amount = float(request.form.get('amount', 0))
    if amount > 0:
        challenge.current_amount += amount
        challenge.update_streak()
        flash(f'Great job! You\'ve maintained a {challenge.streak_days} day streak!', 'success')
        
        if challenge.current_amount >= challenge.target_amount:
            challenge.completed = True
            flash('Congratulations! You have completed the savings challenge!', 'success')
    db.session.commit()
    return redirect(url_for('savings.list_challenges'))

@savings.route('/savings/view/<int:challenge_id>')
@login_required
def view_challenge(challenge_id):
    challenge = SavingsChallenge.query.get_or_404(challenge_id)
    if challenge.user_id != current_user.id:
        flash('You do not have permission to view this challenge.', 'danger')
        return redirect(url_for('savings.list_challenges'))
    return render_template('savings/view.html', challenge=challenge)

@savings.route('/savings/delete/<int:id>')
@login_required
def delete_challenge(id):
    challenge = SavingsChallenge.query.get_or_404(id)
    if challenge.user_id != current_user.id:
        flash('You do not have permission to delete this challenge.', 'danger')
        return redirect(url_for('savings.list_challenges'))
    
    db.session.delete(challenge)
    db.session.commit()
    flash('Savings Challenge deleted successfully!', 'success')
    return redirect(url_for('savings.list_challenges'))