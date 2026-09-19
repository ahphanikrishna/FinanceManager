from flask import Blueprint, request, jsonify
from app.schemas import AccountSchema, AccountCreate, AccountUpdate
from app.models import Account
from app.repository import DatabaseRepository  # Assuming the repository instance is available

# Initialize the Blueprint for the account resource
accounts_bp = Blueprint('accounts', __name__, url_prefix='/api/v1/accounts')

@accounts_bp.route('/', methods=['POST'])
def create_account():
    """Handles creation of a new account."""
    data = request.get_json()
    # Use AccountCreate schema for validation
    try:
        validated_data = AccountCreate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to create account in DB goes here ---

    repo = DatabaseRepository()  # Assuming the repository instance is available
    account = repo.add_record(Account, validated_data.model_dump())
    return jsonify({"message": f"Account {account.name} created successfully"}), 201

@accounts_bp.route('/<int:account_id>', methods=['GET'])
def get_account(account_id):
    """Retrieves an account by ID."""
    # --- Logic to fetch account from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        account = repo.get_by_id(Account, account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"id": account.id, "name": account.name}), 200

@accounts_bp.route('/<int:account_id>', methods=['PATCH'])
def update_account(account_id):
    """Partially updates an account's details."""
    data = request.get_json()
    # Use AccountUpdate schema for partial update validation
    try:
        validated_data = AccountUpdate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to update account in DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        account = repo.get_by_id(Account, account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        updated_account = repo.update_record(account, validated_data.model_dump())
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Account {updated_account.name} updated successfully"}), 200

@accounts_bp.route('/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Deletes an account by ID."""
    # --- Logic to delete account from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        account = repo.get_by_id(Account, account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        repo.delete_record(account)
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Account {account.name} deleted successfully"}), 204

@accounts_bp.route('/', methods=['GET'])
def list_accounts():
    """Lists all accounts."""
    # --- Logic to list accounts from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        accounts = repo.get_all(Account)
        account_list = [{"id": account.id, "name": account.name} for account in accounts]
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify(account_list), 200
