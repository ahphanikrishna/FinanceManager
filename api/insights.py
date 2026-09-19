"""Insights API: monthly spend summaries and trends.

The browser flows use the view layer (with session auth); these
endpoints accept an explicit user_id query parameter for programmatic
access, matching the current API layer's unauthenticated pattern.
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from app.repository import DatabaseRepository
from app.services import insights_service

insights_bp = Blueprint("insights", __name__, url_prefix="/api/v1/insights")


def _default_month():
    # Start on the previous month: it is the last fully settled period.
    previous = date.today().replace(day=1) - timedelta(days=1)
    return previous.strftime("%Y-%m")


def _month_from_request():
    month = request.args.get("month", "")
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return _default_month()


def _user_id_from_request():
    return request.args.get("user_id", type=int)


@insights_bp.route("/summary")
def summary():
    month = _month_from_request()
    user_id = _user_id_from_request()
    if user_id is None:
        return jsonify({"error": "user_id query parameter is required"}), 400

    session = DatabaseRepository().get_session()
    try:
        result = insights_service.monthly_summary(session, user_id, month)
        result["month_over_month"] = insights_service.month_over_month(session, user_id, month)
        result["summary_text"] = insights_service.plain_language_summary(session, user_id, month)
        return jsonify(result)
    finally:
        session.close()


@insights_bp.route("/trends")
def trends():
    user_id = _user_id_from_request()
    if user_id is None:
        return jsonify({"error": "user_id query parameter is required"}), 400

    end_month = _month_from_request()
    try:
        months = max(1, min(int(request.args.get("months", "6")), 24))
    except ValueError:
        months = 6

    session = DatabaseRepository().get_session()
    try:
        series = insights_service.trend(session, user_id, end_month, months)
        return jsonify({"end_month": end_month, "series": series, "anomalies": insights_service.anomalies(series)})
    finally:
        session.close()
