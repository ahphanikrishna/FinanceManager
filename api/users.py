from flask import Blueprint, request, jsonify
from app.schemas import UserSchema, UserCreate, UserUpdate
from app.models import User
from app.repository import DatabaseRepository  # Assuming the repository instance is available

# REST endpoints for user administration. Browser authentication lives in
# views.auth_views so its routes are not forced under the API prefix.
users_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')


@users_bp.route('/create', methods=['POST'])
def create_user():
    """Handles user registration."""
    data = request.get_json()
    # Use UserCreate schema for validation
    try:
        validated_data = UserCreate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to create user in DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    user = repo.add_record(User, validated_data.model_dump())
    return jsonify({"id": user.id, "message": "User registered successfully"}), 201

@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Retrieves a user by ID."""
    # --- Logic to fetch user from DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    user = repo.get_by_id(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"id": user.id, "username": user.username, "email": user.email}), 200

@users_bp.route('/<int:user_id>', methods=['PATCH'])
def update_user(user_id):
    """Partially updates a user's details."""
    data = request.get_json()
    # Use UserUpdate schema for partial update validation
    try:
        validated_data = UserUpdate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to update user in DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    user = repo.get_by_id(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    updated_user = repo.update_record(user, validated_data.model_dump())
    return jsonify({"id": updated_user.id, "message": "User updated successfully"}), 200

@users_bp.route('/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user by ID."""
    # --- Logic to delete user from DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    success = repo.delete_record(User, user_id)
    if not success:
        return jsonify({"error": "User not found or could not be deleted"}), 404

    return jsonify({"message": "User deleted successfully"}), 204

