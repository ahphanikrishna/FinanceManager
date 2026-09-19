from app.models import Transaction # Import the Model
from app.repository import DatabaseRepository # Assume the repository instance is available via a module variable like app_db_repository
from flask import Blueprint, request, jsonify

from app.schemas import TransactionCreate, TransactionUpdate

# Initialize the Blueprint for the transaction resource
transactions_bp = Blueprint('transactions', __name__, url_prefix='/api/v1/transactions')

@transactions_bp.route('/', methods=['POST'])
def create_transaction():
    """Handles creation of a new transaction."""
    data = request.get_json()
    # Use TransactionCreate schema for validation
    try:
        validated_data = TransactionCreate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to create transaction in DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    transaction = repo.add_record(Transaction, validated_data.model_dump())
    return jsonify({"id": transaction.id, "message": "Transaction created successfully"}), 201

@transactions_bp.route('/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Retrieves a transaction by ID."""
    # --- Logic to fetch transaction from DB goes here ---
    return jsonify({"id": transaction_id, "amount": 100.00, "type": "Income"}), 200

@transactions_bp.route('/<int:transaction_id>', methods=['PATCH'])
def update_transaction(transaction_id):
    """Partially updates a transaction's details."""
    data = request.get_json()
    # Use TransactionUpdate schema for partial update validation
    try:
        validated_data = TransactionUpdate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to update transaction in DB goes here ---
    return jsonify({"message": f"Transaction {transaction_id} updated successfully"}), 200

@transactions_bp.route('/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Deletes a transaction by ID."""
    # --- Logic to delete transaction from DB goes here ---
    return jsonify({"message": f"Transaction {transaction_id} deleted successfully"}), 204
