from flask import Blueprint, request, jsonify
from app.schemas import CategorySchema, CategoryCreate, CategoryUpdate
from app.models import Category
from app.repository import DatabaseRepository

# Initialize the Blueprint for the category resource
categories_bp = Blueprint('categories', __name__, url_prefix='/api/v1/categories')

@categories_bp.route('/', methods=['POST'])
def create_category():
    """Handles creation of a new category."""
    data = request.get_json()
    # Use CategoryCreate schema for validation
    try:
        validated_data = CategoryCreate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to create category in DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    category = repo.add_record(Category, validated_data.model_dump())
    return jsonify({"id": category.id, "message": "Category created successfully"}), 201

@categories_bp.route('/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """Retrieves a category by ID."""
    # --- Logic to fetch category from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        category = repo.get_by_id(Category, category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"id": category.id, "name": category.name}), 200

@categories_bp.route('/<int:category_id>', methods=['PATCH'])
def update_category(category_id):
    """Partially updates a category's details."""
    data = request.get_json()
    # Use CategoryUpdate schema for partial update validation
    try:
        validated_data = CategoryUpdate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to update category in DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        category = repo.get_by_id(Category, category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
        updated_category = repo.update_record(category, validated_data.model_dump())
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Category {updated_category.name} updated successfully"}), 200

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Deletes a category by ID."""
    # --- Logic to delete category from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        category = repo.get_by_id(Category, category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
        repo.delete_record(category)
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Category {category.name} deleted successfully"}), 204

@categories_bp.route('/', methods=['GET'])
def list_categories():
    """Lists all categories."""
    # --- Logic to list categories from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        categories = repo.get_all(Category)
        category_list = [{"id": cat.id, "name": cat.name} for cat in categories]
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify(category_list), 200

