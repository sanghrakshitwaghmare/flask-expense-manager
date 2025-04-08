from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, RecurringExpense, Expense, Income
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, SelectField, DateField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Length
from datetime import datetime, timedelta

recurring = Blueprint('recurring', __name__)

class RecurringTransactionForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    amount = FloatField('Amount', validators=[DataRequired()])
    category = SelectField('Category', validators=[DataRequired()])
    frequency = SelectField('Frequency', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()], default=datetime.utcnow)
    description = TextAreaField('Description', validators=[Length(max=200)])
    is_expense = BooleanField('Is this an expense?', default=True)
    active = BooleanField('Active', default=True)

def calculate_next_due_date(start_date, frequency):
    today = datetime.utcnow().date()
    if frequency == 'daily':
        return today + timedelta(days=1)
    elif frequency == 'weekly':
        return today + timedelta(days=7)
    elif frequency == 'monthly':
        if today.month == 12:
            return today.replace(year=today.year + 1, month=1)
        return today.replace(month=today.month + 1)
    else:  # yearly
        return today.replace(year=today.year + 1)

def process_due_transactions():
    """Process all due recurring transactions"""
    today = datetime.utcnow().date()
    recurring_transactions = RecurringExpense.query.filter(
        RecurringExpense.active == True,
        RecurringExpense.next_due_date <= today
    ).all()

    for transaction in recurring_transactions:
        if transaction.is_expense:
            expense = Expense(
                amount=transaction.amount,
                category_id=transaction.category,
                description=f'Recurring: {transaction.name}',
                date=datetime.utcnow(),
                user_id=transaction.user_id
            )
            db.session.add(expense)
        else:
            income = Income(
                amount=transaction.amount,
                source=transaction.name,
                description=f'Recurring: {transaction.description}',
                date=datetime.utcnow(),
                user_id=transaction.user_id
            )
            db.session.add(income)

        # Update next due date
        transaction.next_due_date = calculate_next_due_date(
            transaction.next_due_date,
            transaction.frequency
        )

    db.session.commit()

@recurring.route('/recurring')
@login_required
def list_recurring():
    process_due_transactions()  # Process any due transactions
    transactions = RecurringExpense.query.filter_by(user_id=current_user.id).all()
    return render_template('recurring/list.html', transactions=transactions)

@recurring.route('/recurring/add', methods=['GET', 'POST'])
@login_required
def add_recurring():
    form = RecurringTransactionForm()
    form.category.choices = [(c.id, c.name) for c in current_user.expense_categories]

    if form.validate_on_submit():
        transaction = RecurringExpense(
            name=form.name.data,
            amount=form.amount.data,
            category=form.category.data,
            frequency=form.frequency.data,
            next_due_date=form.start_date.data,
            description=form.description.data,
            is_expense=form.is_expense.data,
            active=form.active.data,
            user_id=current_user.id
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Recurring transaction added successfully!', 'success')
        return redirect(url_for('recurring.list_recurring'))

    return render_template('recurring/form.html', form=form, title='Add Recurring Transaction')

@recurring.route('/recurring/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_recurring(id):
    transaction = RecurringExpense.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        flash('You do not have permission to edit this transaction.', 'danger')
        return redirect(url_for('recurring.list_recurring'))

    form = RecurringTransactionForm(obj=transaction)
    form.category.choices = [(c.id, c.name) for c in current_user.expense_categories]

    if form.validate_on_submit():
        transaction.name = form.name.data
        transaction.amount = form.amount.data
        transaction.category = form.category.data
        transaction.frequency = form.frequency.data
        transaction.next_due_date = form.start_date.data
        transaction.description = form.description.data
        transaction.is_expense = form.is_expense.data
        transaction.active = form.active.data
        db.session.commit()
        flash('Recurring transaction updated successfully!', 'success')
        return redirect(url_for('recurring.list_recurring'))

    return render_template('recurring/form.html', form=form, title='Edit Recurring Transaction')

@recurring.route('/recurring/toggle/<int:id>')
@login_required
def toggle_recurring(id):
    transaction = RecurringExpense.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        flash('You do not have permission to modify this transaction.', 'danger')
        return redirect(url_for('recurring.list_recurring'))

    transaction.active = not transaction.active
    db.session.commit()
    status = 'activated' if transaction.active else 'deactivated'
    flash(f'Recurring transaction {status} successfully!', 'success')
    return redirect(url_for('recurring.list_recurring'))