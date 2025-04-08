from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length
from models import db, ExpenseCategory

categories = Blueprint('categories', __name__)

DEFAULT_EXPENSE_CATEGORIES = [
    {'name': 'Food & Dining', 'description': 'Groceries, restaurants, and food delivery'},
    {'name': 'Transportation', 'description': 'Public transit, fuel, car maintenance'},
    {'name': 'Housing', 'description': 'Rent, mortgage, utilities, maintenance'},
    {'name': 'Healthcare', 'description': 'Medical expenses, medications, insurance'},
    {'name': 'Entertainment', 'description': 'Movies, games, streaming services'},
    {'name': 'Shopping', 'description': 'Clothing, electronics, personal items'},
    {'name': 'Education', 'description': 'Tuition, books, courses'},
    {'name': 'Bills & Utilities', 'description': 'Phone, internet, electricity'},
    {'name': 'Travel', 'description': 'Vacations, hotels, flights'},
    {'name': 'Others', 'description': 'Miscellaneous expenses'}
]

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Description', validators=[Length(max=200)])
    submit = SubmitField('Submit')

@categories.route('/categories')
@login_required
def list_categories():
    categories = ExpenseCategory.query.filter_by(user_id=current_user.id).all()
    return render_template('categories/list.html', categories=categories)

@categories.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        category = ExpenseCategory(
            name=form.name.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('categories.list_categories'))
    return render_template('categories/form.html', form=form, title='Add Category')

@categories.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = ExpenseCategory.query.get_or_404(id)
    if category.user_id != current_user.id:
        flash('You do not have permission to edit this category.', 'danger')
        return redirect(url_for('categories.list_categories'))
    
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('categories.list_categories'))
    return render_template('categories/form.html', form=form, title='Edit Category')

@categories.route('/categories/delete/<int:id>')
@login_required
def delete_category(id):
    category = ExpenseCategory.query.get_or_404(id)
    if category.user_id != current_user.id:
        flash('You do not have permission to delete this category.', 'danger')
        return redirect(url_for('categories.list_categories'))
    
    if category.is_default:
        flash('Cannot delete default categories.', 'danger')
        return redirect(url_for('categories.list_categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('categories.list_categories'))

@categories.route('/categories/initialize-defaults')
@login_required
def initialize_default_categories():
    existing_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id,
        is_default=True
    ).all()
    
    if not existing_categories:
        for cat in DEFAULT_EXPENSE_CATEGORIES:
            category = ExpenseCategory(
                name=cat['name'],
                description=cat['description'],
                is_default=True,
                user_id=current_user.id
            )
            db.session.add(category)
        db.session.commit()
        flash('Default categories have been initialized!', 'success')
    else:
        flash('Default categories already exist.', 'info')
    
    return redirect(url_for('categories.list_categories'))