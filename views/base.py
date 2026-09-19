from datetime import date, datetime

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.models import Balance, Transaction
from app.repository import DatabaseRepository

home_bp = Blueprint('home_bp', __name__, url_prefix='/')

@home_bp.route('/dashboard')
@login_required
def dashboard():
    repository = DatabaseRepository()
    user_id = current_user.get_id()
    requested_month = request.args.get('month', '')
    try:
        selected_month = datetime.strptime(requested_month, '%Y-%m').strftime('%Y-%m')
    except ValueError:
        selected_month = date.today().strftime('%Y-%m')

    transactions = [
        transaction
        for transaction in repository.get_all(Transaction)
        if str(transaction.user_id) == user_id
        and transaction.date
        and transaction.date.strftime('%Y-%m') == selected_month
    ]
    balances = [
        balance
        for balance in repository.get_all(Balance)
        if str(balance.user_id) == user_id
        and str(balance.month).startswith(selected_month)
    ]

    totals = {
        'income': 0.0,
        'expenses': 0.0,
        'investments': 0.0,
        'transfers': 0.0,
    }
    total_by_type = {
        'income': 'income',
        'expenditure': 'expenses',
        'expense': 'expenses',
        'investment': 'investments',
        'transfer': 'transfers',
    }
    for transaction in transactions:
        total_key = total_by_type.get((transaction.type or '').strip().lower())
        if total_key:
            totals[total_key] += transaction.amount or 0.0

    return render_template(
        'dashboard.html',
        totals=totals,
        balances=balances,
        selected_month=selected_month,
    )

@home_bp.route('/accounts')
def accounts_page():
    return render_template('manage_entities.html')