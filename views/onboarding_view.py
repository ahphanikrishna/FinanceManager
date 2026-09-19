"""First-run onboarding wizard.

Guided setup flow: profile -> members -> accounts -> categories -> budget.
Progress is persisted per user in the onboarding table so the completion
state survives page reloads and is visible from the dashboard.
"""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import Account, Category, Member
from app.repository import DatabaseRepository
from app.services import onboarding_service

onboarding_bp = Blueprint("onboarding", __name__)


def _session():
    return DatabaseRepository().get_session()


@onboarding_bp.route("/onboarding")
@login_required
def index():
    session = _session()
    try:
        progress = onboarding_service.ensure_progress(session, current_user.id)
        active_step = onboarding_service.current_step(progress)
        members = session.query(Member).filter(Member.user_id == current_user.id).order_by(Member.name).all()
        accounts = session.query(Account).filter(Account.user_id == current_user.id).order_by(Account.account_name).all()
        categories = session.query(Category).filter(Category.user_id == current_user.id).order_by(Category.Category).all()
        return render_template(
            "onboarding.html",
            progress=progress,
            active_step=active_step,
            completed=onboarding_service.is_complete(progress),
            steps=onboarding_service.STEP_LABELS,
            step_members=onboarding_service.STEP_MEMBERS,
            step_accounts=onboarding_service.STEP_ACCOUNTS,
            step_categories=onboarding_service.STEP_CATEGORIES,
            step_budget=onboarding_service.STEP_BUDGET,
            members=members,
            accounts=accounts,
            categories=categories,
        )
    finally:
        session.close()


@onboarding_bp.route("/onboarding/step", methods=["POST"])
@login_required
def advance_step():
    session = _session()
    try:
        progress = onboarding_service.ensure_progress(session, current_user.id)
        active_step = onboarding_service.current_step(progress)
        requirement_step = {
            onboarding_service.STEP_MEMBERS: "members",
            onboarding_service.STEP_ACCOUNTS: "accounts",
            onboarding_service.STEP_CATEGORIES: "categories",
        }.get(active_step)
        if requirement_step:
            counts = onboarding_service.entity_counts(session, current_user.id)
            if counts[requirement_step] == 0:
                label = requirement_step[:-1]
                flash(f"Add at least one {label} to continue.", "error")
                return redirect(url_for("onboarding.index"))
        progress.current_step = active_step
        session.commit()
    finally:
        session.close()
    return redirect(url_for("onboarding.index"))


@onboarding_bp.route("/onboarding/members", methods=["POST"])
@login_required
def add_member():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Member name is required.", "error")
        return redirect(url_for("onboarding.index"))
    session = _session()
    try:
        session.add(Member(name=name, user_id=current_user.id))
        session.commit()
        flash("Member added.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash("Could not add the member.", "error")
    finally:
        session.close()
    return redirect(url_for("onboarding.index"))


@onboarding_bp.route("/onboarding/accounts", methods=["POST"])
@login_required
def add_account():
    account_name = request.form.get("account_name", "").strip()
    account_type = request.form.get("account_type", "").strip()
    if not account_name or not account_type:
        flash("Account name and type are required.", "error")
        return redirect(url_for("onboarding.index"))
    session = _session()
    try:
        session.add(Account(account_name=account_name, account_type=account_type, user_id=current_user.id))
        session.commit()
        flash("Account added.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash("Could not add the account.", "error")
    finally:
        session.close()
    return redirect(url_for("onboarding.index"))


@onboarding_bp.route("/onboarding/categories", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("Category", "").strip()
    subcategory = request.form.get("subcategory", "").strip() or name
    category_type = request.form.get("type", "").strip()
    if not name or category_type not in ("Expenditure", "Income", "Investment", "Transfer"):
        flash("Category name and a valid type are required.", "error")
        return redirect(url_for("onboarding.index"))
    session = _session()
    try:
        session.add(Category(Category=name, subcategory=subcategory, type=category_type, user_id=current_user.id))
        session.commit()
        flash("Category added.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash("Could not add the category.", "error")
    finally:
        session.close()
    return redirect(url_for("onboarding.index"))


@onboarding_bp.route("/onboarding/complete", methods=["POST"])
@login_required
def complete():
    session = _session()
    try:
        progress = onboarding_service.ensure_progress(session, current_user.id)
        raw_budget = request.form.get("monthly_budget", "").strip()
        monthly_budget = None
        if raw_budget:
            try:
                monthly_budget = float(raw_budget)
            except ValueError:
                flash("Monthly budget must be a number.", "error")
                return redirect(url_for("onboarding.index"))
        can_finish, message = onboarding_service.can_complete(session, current_user.id)
        if not can_finish:
            flash(message, "error")
            return redirect(url_for("onboarding.index"))
        progress.current_step = onboarding_service.TOTAL_STEPS
        progress.monthly_budget = monthly_budget
        progress.completed_at = progress.completed_at or datetime.now()
        session.commit()
        flash("Setup complete. Welcome aboard!", "success")
    finally:
        session.close()
    return redirect(url_for("onboarding.index"))
