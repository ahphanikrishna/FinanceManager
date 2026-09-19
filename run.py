import os
import argparse
import sys


def select_environment():
    parser = argparse.ArgumentParser(description="Run FinanceManager in a selected environment.")
    parser.add_argument(
        "--env",
        dest="environment",
        choices=("dev", "qa", "prod"),
        help="Environment to load: dev, qa, or prod.",
    )
    args, _ = parser.parse_known_args()
    environment = args.environment or os.environ.get("APP_ENV", "dev").lower()
    if environment not in {"dev", "qa", "prod"}:
        environment = "dev"
    os.environ["APP_ENV"] = environment
    return environment


ACTIVE_ENV = select_environment()

from flask import Flask, render_template
from flask_login import LoginManager, AnonymousUserMixin
from api import transactions, categories, accounts, members, users
from app.database import Base
from app.repository import DatabaseRepository, init_db_and_repo
from app.models import User  # Make sure to import your User model
from views.base import home_bp
from views.auth_views import auth_bp
from views.settings_view import settings_bp
from views.transactions_view import transactions_view_bp
from views.onboarding_view import onboarding_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Required for sessions
app.db_repository = DatabaseRepository()

# 1. Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# 2. Define user loader callback
@login_manager.user_loader
def load_user(user_id):
    repo = getattr(app, 'db_repository', DatabaseRepository())
    return repo.get_by_id(User, int(user_id))

# Register blueprints
app.register_blueprint(transactions.transactions_bp)  
app.register_blueprint(categories.categories_bp)  
app.register_blueprint(accounts.accounts_bp)  
app.register_blueprint(members.members_bp)
app.register_blueprint(users.users_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(home_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(transactions_view_bp)
app.register_blueprint(onboarding_bp)

@app.route('/')
def index():
    return render_template('base.html')

if __name__ == '__main__':
    if not any(argument.startswith("--env") for argument in sys.argv[1:]) and not os.environ.get("APP_ENV"):
        print("Select environment:")
        print("1. dev")
        print("2. qa")
        print("3. prod")
        choice = input("Enter 1, 2, or 3 [1]: ").strip() or "1"
        selected_environment = {"1": "dev", "2": "qa", "3": "prod"}.get(choice)
        if selected_environment is None:
            raise SystemExit("Invalid environment selection. Choose 1, 2, or 3.")

        os.execv(
            sys.executable,
            [sys.executable, sys.argv[0], "--env", selected_environment, *sys.argv[1:]],
        )

    init_db_and_repo(app)
    app.run(debug=ACTIVE_ENV != "prod")