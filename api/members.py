from flask import Blueprint, request, jsonify
from app.schemas import MemberSchema, MemberCreate, MemberUpdate
from app.models import Member
from app.repository import DatabaseRepository  # Assuming the repository instance is available

# Initialize the Blueprint for the member resource
members_bp = Blueprint('members', __name__, url_prefix='/api/v1/members')

@members_bp.route('/', methods=['POST'])
def create_member():
    """Handles creation of a new member."""
    data = request.get_json()
    # Use MemberCreate schema for validation
    try:
        validated_data = MemberCreate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to create member in DB goes here ---
    repo = DatabaseRepository()  # Assuming the repository instance is available
    member = repo.add_record(Member, validated_data.model_dump())
    return jsonify({"message": f"Member {member.name} created successfully"}), 201

@members_bp.route('/<int:member_id>', methods=['GET'])
def get_member(member_id):
    """Retrieves a member by ID."""
    # --- Logic to fetch member from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        member = repo.get_by_id(Member, member_id)
        if not member:
            return jsonify({"error": "Member not found"}), 404
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"id": member.id, "name": member.name}), 200

@members_bp.route('/<int:member_id>', methods=['PATCH'])
def update_member(member_id):
    """Partially updates a member's details."""
    data = request.get_json()
    # Use MemberUpdate schema for partial update validation
    try:
        validated_data = MemberUpdate(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    # --- Logic to update member in DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        member = repo.get_by_id(Member, member_id)
        if not member:
            return jsonify({"error": "Member not found"}), 404
        updated_member = repo.update_record(member, validated_data.model_dump())
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Member {updated_member.name} updated successfully"}), 200

@members_bp.route('/<int:member_id>', methods=['DELETE'])
def delete_member(member_id):
    """Deletes a member by ID."""
    # --- Logic to delete member from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        member = repo.get_by_id(Member, member_id)
        if not member:
            return jsonify({"error": "Member not found"}), 404
        repo.delete_record(member)
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify({"message": f"Member {member.name} deleted successfully"}), 204

@members_bp.route('/', methods=['GET'])
def list_members():
    """Lists all members."""
    # --- Logic to list members from DB goes here ---
    try:
        repo = DatabaseRepository()  # Assuming the repository instance is available
        members = repo.get_all(Member)
        member_list = [{"id": member.id, "name": member.name} for member in members]
    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500
    return jsonify(member_list), 200