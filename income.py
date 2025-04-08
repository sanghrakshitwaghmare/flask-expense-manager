from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Income
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Length
from datetime import datetime

incomes = Blueprint('incomes', __name__)

class IncomeForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired()])
    source = StringField('Source', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Description', validators=[Length(max=200)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)
    submit = SubmitField('Submit')

@incomes.route('/incomes')
@login_required
def list_incomes():
    incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc()).all()
    total_income = sum(income.amount for income in incomes)
    return render_template('incomes/list.html', incomes=incomes, total_income=total_income)

@incomes.route('/incomes/add', methods=['GET', 'POST'])
@login_required
def add_income():
    form = IncomeForm()
    if form.validate_on_submit():
        income = Income(
            amount=form.amount.data,
            source=form.source.data,
            description=form.description.data,
            date=form.date.data,
            user_id=current_user.id
        )
        db.session.add(income)
        db.session.commit()
        flash('Income added successfully!', 'success')
        return redirect(url_for('incomes.list_incomes'))
    return render_template('incomes/form.html', form=form, title='Add Income')

@incomes.route('/incomes/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_income(id):
    income = Income.query.get_or_404(id)
    if income.user_id != current_user.id:
        flash('You do not have permission to edit this income.', 'danger')
        return redirect(url_for('incomes.list_incomes'))
    
    form = IncomeForm(obj=income)
    if form.validate_on_submit():
        income.amount = form.amount.data
        income.source = form.source.data
        income.description = form.description.data
        income.date = form.date.data
        db.session.commit()
        flash('Income updated successfully!', 'success')
        return redirect(url_for('incomes.list_incomes'))
    return render_template('incomes/form.html', form=form, title='Edit Income')

@incomes.route('/incomes/delete/<int:id>')
@login_required
def delete_income(id):
    income = Income.query.get_or_404(id)
    if income.user_id != current_user.id:
        flash('You do not have permission to delete this income.', 'danger')
        return redirect(url_for('incomes.list_incomes'))
    
    db.session.delete(income)
    db.session.commit()
    flash('Income deleted successfully!', 'success')
    return redirect(url_for('incomes.list_incomes'))

@incomes.route('/incomes/sources')
@login_required
def income_sources():
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    sources = {}
    for income in incomes:
        if income.source in sources:
            sources[income.source] += income.amount
        else:
            sources[income.source] = income.amount
    return render_template('incomes/sources.html', sources=sources)