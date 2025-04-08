from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Expense, ExpenseCategory
from flask_wtf import FlaskForm
from wtforms import FloatField, TextAreaField, DateField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length
from datetime import datetime

expenses = Blueprint('expenses', __name__)

class ExpenseForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=200)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super(ExpenseForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(c.id, c.name) for c in ExpenseCategory.query.filter_by(user_id=current_user.id).all()]

@expenses.route('/expenses')
@login_required
def list_expenses():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    total_expenses = sum(expense.amount for expense in expenses)
    return render_template('expenses/list.html', expenses=expenses, total_expenses=total_expenses)

@expenses.route('/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    form = ExpenseForm()
    if form.validate_on_submit():
        expense = Expense(
            amount=form.amount.data,
            category_id=form.category_id.data,
            description=form.description.data,
            date=form.date.data,
            user_id=current_user.id
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    return render_template('expenses/form.html', form=form, title='Add Expense')

@expenses.route('/expenses/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('You do not have permission to edit this expense.', 'danger')
        return redirect(url_for('expenses.list_expenses'))
    
    form = ExpenseForm(obj=expense)
    if form.validate_on_submit():
        expense.amount = form.amount.data
        expense.category_id = form.category_id.data
        expense.description = form.description.data
        expense.date = form.date.data
        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    form.category_id.data = expense.category_id
    return render_template('expenses/form.html', form=form, title='Edit Expense')

@expenses.route('/expenses/delete/<int:id>')
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('You do not have permission to delete this expense.', 'danger')
        return redirect(url_for('expenses.list_expenses'))
    
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('expenses.list_expenses'))

@expenses.route('/expenses/categories')
@login_required
def expense_categories():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    categories = {}
    for expense in expenses:
        if expense.category in categories:
            categories[expense.category] += expense.amount
        else:
            categories[expense.category] = expense.amount
    return render_template('expenses/categories.html', categories=categories)