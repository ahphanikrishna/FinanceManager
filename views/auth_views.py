from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import User
from app.repository import DatabaseRepository
from app.security import get_password_hash, verify_password


auth_bp = Blueprint("auth", __name__)


def _repository():
    return DatabaseRepository()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home_bp.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        repository = _repository()
        user = repository.get_by_field(User, "username", identifier)
        if user is None:
            user = repository.get_by_field(User, "email", identifier.lower())

        if user is None or not verify_password(password, user.hashed_password):
            flash("Invalid username, email, or password.", "error")
            return render_template("auth.html"), 401

        login_user(user)
        return redirect(url_for("home_bp.dashboard"))

    return render_template("auth.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("Username, email, and password are required.", "error")
        return render_template("auth.html", active_tab="register"), 400

    repository = _repository()
    if repository.get_by_field(User, "username", username) or repository.get_by_field(User, "email", email):
        flash("That username or email is already registered.", "error")
        return render_template("auth.html", active_tab="register"), 409

    user = repository.add_record(
        User,
        {"username": username, "email": email, "hashed_password": get_password_hash(password)},
    )
    login_user(user)
    flash("Account created successfully.", "success")
    return redirect(url_for("home_bp.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))