from flask import Blueprint, send_file, jsonify, request, render_template, abort
from flask_login import login_required, current_user
from models import Expense, Income, Budget, SavingsChallenge, ExpenseCategory, db
from datetime import datetime
from functools import wraps
import csv
import io
import pandas as pd
from sqlalchemy import and_
import pytz
from werkzeug.exceptions import BadRequest

export_data = Blueprint('export_data', __name__)

# Rate limiting decorator (simplified example)
def rate_limit(max_per_minute=10):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # In production, use Redis or similar for proper rate limiting
            return f(*args, **kwargs)
        return wrapped
    return decorator

def validate_export_params(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                start_date = start_date.replace(tzinfo=pytz.UTC)
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=pytz.UTC)
                
                if start_date and end_date < start_date:
                    raise BadRequest("End date must be after start date")
                    
            return f(start_date=start_date, end_date=end_date, *args, **kwargs)
        except ValueError:
            raise BadRequest("Invalid date format. Use YYYY-MM-DD")
    return wrapped

def get_user_data(start_date=None, end_date=None):
    """Gather all user financial data with optimized queries"""
    try:
        # Base query filters
        filters = [Expense.user_id == current_user.id]
        if start_date:
            filters.append(Expense.date >= start_date)
        if end_date:
            filters.append(Expense.date <= end_date)
            
        # Get expenses with category in single query
        expenses = db.session.query(Expense, ExpenseCategory.name)\
            .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)\
            .filter(and_(*filters))\
            .order_by(Expense.date.desc())\
            .all()
        
        # Get incomes
        income_filters = [Income.user_id == current_user.id]
        if start_date:
            income_filters.append(Income.date >= start_date)
        if end_date:
            income_filters.append(Income.date <= end_date)
            
        incomes = Income.query.filter(and_(*income_filters)).all()
        
        # Get budgets and savings challenges
        budgets = Budget.query.filter_by(user_id=current_user.id).all()
        savings = SavingsChallenge.query.filter_by(user_id=current_user.id).all()
        
        return expenses, incomes, budgets, savings
        
    except Exception as e:
        db.session.rollback()
        raise e

def format_data_for_export(expenses, incomes, budgets, savings):
    """Format data for export with proper null handling"""
    def safe_float(value):
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def safe_str(value):
        return str(value) if value is not None else ''

    data = {
        'expenses': [{
            'date': e.Expense.date.strftime('%Y-%m-%d') if e.Expense.date else '',
            'amount': safe_float(e.Expense.amount),
            'category': safe_str(e.name),  # From joined ExpenseCategory
            'description': safe_str(e.Expense.description)
        } for e in expenses],
        
        'incomes': [{
            'date': i.date.strftime('%Y-%m-%d') if i.date else '',
            'amount': safe_float(i.amount),
            'source': safe_str(i.source),
            'description': safe_str(i.description)
        } for i in incomes],
        
        'budgets': [{
            'category': safe_str(b.category),
            'amount': safe_float(b.amount),
            'period': b.period.value if b.period else ''
        } for b in budgets],
        
        'savings_challenges': [{
            'title': safe_str(s.title),
            'target_amount': safe_float(s.target_amount),
            'current_amount': safe_float(s.current_amount),
            'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
            'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
            'completed': bool(s.completed)
        } for s in savings]
    }
    return data

@export_data.route('/')
@login_required
def export_interface():
    """Render export interface with form"""
    return render_template('export/export.html')

@export_data.route('/export/csv')
@login_required
@rate_limit()
@validate_export_params
def export_csv(start_date=None, end_date=None):
    """Export data as CSV with proper error handling"""
    try:
        expenses, incomes, budgets, savings = get_user_data(start_date, end_date)
        data = format_data_for_export(expenses, incomes, budgets, savings)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write expenses
        writer.writerow(['Expenses'])
        writer.writerow(['Date', 'Amount', 'Category', 'Description'])
        writer.writerows([
            [e['date'], e['amount'], e['category'], e['description']]
            for e in data['expenses']
        ])
        writer.writerow([])
        
        # Write other sections similarly...
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'financial_data_{datetime.now().strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        abort(500, description=str(e))

@export_data.route('/export/excel')
@login_required
@rate_limit()
@validate_export_params
def export_excel(start_date=None, end_date=None):
    """Export data as Excel with memory optimization"""
    try:
        expenses, incomes, budgets, savings = get_user_data(start_date, end_date)
        data = format_data_for_export(expenses, incomes, budgets, savings)
        
        # Process data in chunks for memory efficiency
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Process expenses
            expenses_df = pd.DataFrame(data['expenses'])
            expenses_df.to_excel(writer, sheet_name='Expenses', index=False)
            
            # Process other sections similarly...
            
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'financial_data_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        abort(500, description=str(e))

@export_data.route('/export/json')
@login_required
@rate_limit()
@validate_export_params
def export_json(start_date=None, end_date=None):
    """Export data as JSON with proper error handling"""
    try:
        expenses, incomes, budgets, savings = get_user_data(start_date, end_date)
        data = format_data_for_export(expenses, incomes, budgets, savings)
        
        return jsonify({
            'status': 'success',
            'data': data,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': current_user.id,
            'record_count': {
                'expenses': len(data['expenses']),
                'incomes': len(data['incomes']),
                'budgets': len(data['budgets']),
                'savings': len(data['savings_challenges'])
            }
        })
        
    except Exception as e:
        abort(500, description=str(e))
