"""Categorization suggestion API."""
from flask import Blueprint, jsonify, request

from app.repository import DatabaseRepository
from app.services import categorization_service

suggestions_bp = Blueprint("suggestions", __name__, url_prefix="/api/v1/suggestions")


def _user_id_from_body():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    return int(user_id) if user_id is not None else None


@suggestions_bp.route("/categorize", methods=["POST"])
def categorize():
    payload = request.get_json(silent=True) or {}
    user_id = _user_id_from_body()
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    session = DatabaseRepository().get_session()
    try:
        suggestions = categorization_service.suggest_categories(
            session,
            user_id,
            description=payload.get("description", ""),
            member=payload.get("member"),
            account=payload.get("account"),
            tx_type=payload.get("type"),
        )
        return jsonify({"suggestions": suggestions})
    finally:
        session.close()


@suggestions_bp.route("/apply", methods=["POST"])
def apply_categorization():
    payload = request.get_json(silent=True) or {}
    user_id = _user_id_from_body()
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    threshold = float(payload.get("threshold", categorization_service.DEFAULT_THRESHOLD))
    limit = int(payload.get("limit", 200))
    month = payload.get("month")

    session = DatabaseRepository().get_session()
    try:
        report = categorization_service.auto_categorize(session, user_id, threshold=threshold, limit=limit, month=month)
        return jsonify(report)
    finally:
        session.close()
