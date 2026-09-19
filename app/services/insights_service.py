"""Monthly spend insights service.

Computes spend summaries, category breakdowns, month-over-month
comparisons, short-term trends, and plain-language summaries from
the user's historical transactions. Pure reads, scoped per user.
"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import Onboarding, Transaction

TREND_MONTHS = 6


def _month_bounds(month: str):
    month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start, month_end


def previous_month(month: str) -> str:
    start, _ = _month_bounds(month)
    if start.month == 1:
        return f"{start.year - 1}-12"
    return f"{start.year}-{start.month - 1:02d}"


def _transactions_between(session: Session, user_id, start, end):
    return (
        session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .all()
    )


def _month_totals(transactions) -> dict:
    """Aggregate a list of transactions into standard totals."""
    totals = {"income": 0.0, "expenses": 0.0, "investments": 0.0, "transfers": 0.0}
    by_category = {}
    for tx in transactions:
        key = (tx.type or "").strip().lower()
        amount = abs(tx.amount or 0.0)
        if key == "income":
            totals["income"] += amount
        elif key in ("expenditure", "expense"):
            totals["expenses"] += amount
            category = (tx.category or "Uncategorized").strip()
            entry = by_category.setdefault(category, {"total": 0.0, "count": 0})
            entry["total"] += amount
            entry["count"] += 1
        elif key == "investment":
            totals["investments"] += amount
        elif key == "transfer":
            totals["transfers"] += amount
    categories = [
        {"category": name, "total": data["total"], "count": data["count"]}
        for name, data in sorted(by_category.items(), key=lambda item: item[1]["total"], reverse=True)
    ]
    return {"totals": totals, "by_category": categories}


def monthly_summary(session: Session, user_id, month: str) -> dict:
    """Spend breakdown for one month: totals + category rollup."""
    start, end = _month_bounds(month)
    transactions = _transactions_between(session, user_id, start, end)
    result = _month_totals(transactions)
    result["month"] = month
    result["transaction_count"] = len(transactions)
    return result


def month_over_month(session: Session, user_id, month: str) -> dict:
    """Expense delta vs the previous month."""
    current = monthly_summary(session, user_id, month)["totals"]["expenses"]
    previous_month_key = previous_month(month)
    previous = monthly_summary(session, user_id, previous_month_key)["totals"]["expenses"]
    delta = current - previous
    delta_pct = (delta / previous * 100.0) if previous else None
    return {
        "month": month,
        "previous_month": previous_month_key,
        "current": current,
        "previous": previous,
        "delta": delta,
        "delta_pct": delta_pct,
    }


def trend(session: Session, user_id, end_month: str, months: int = TREND_MONTHS) -> list:
    """Per-month income/expense series ending at end_month (oldest first)."""
    end_start, _ = _month_bounds(end_month)
    series = []
    cursor = end_start
    while len(series) < months:
        start, end = _month_bounds(cursor.strftime("%Y-%m"))
        data = _month_totals(_transactions_between(session, user_id, start, end))
        series.append({
            "month": cursor.strftime("%Y-%m"),
            "income": data["totals"]["income"],
            "expenses": data["totals"]["expenses"],
            "transaction_count": 0,
        })
        if start.month == 1:
            cursor = start.replace(year=start.year - 1, month=12)
        else:
            cursor = start.replace(month=start.month - 1)
    return list(reversed(series))


def anomalies(series: list, spike_factor: float = 1.5) -> list:
    """Months whose expenses spike well above the trailing average.

    Simple, explainable rule: needs at least two other data points and
    flags months above spike_factor * average-of-others.
    """
    flagged = []
    for point in series:
        others = [p["expenses"] for p in series if p["month"] != point["month"]]
        if len(others) < 2 or point["expenses"] <= 0:
            continue
        average = sum(others) / len(others)
        if average > 0 and point["expenses"] > average * spike_factor:
            flagged.append(point["month"])
    return flagged


def _budget(session: Session, user_id):
    progress = session.query(Onboarding).filter(Onboarding.user_id == user_id).first()
    return progress.monthly_budget if progress is not None else None


def plain_language_summary(session: Session, user_id, month: str) -> str:
    """One-paragraph human summary for the dashboard."""
    summary = monthly_summary(session, user_id, month)
    totals = summary["totals"]
    if summary["transaction_count"] == 0:
        return f"No transactions recorded for {month} yet."

    sentences = [f"You spent ₹{totals['expenses']:,.2f} in {month}."]
    if totals["income"]:
        sentences.append(f"You took in ₹{totals['income']:,.2f} of income.")

    mom = month_over_month(session, user_id, month)
    if mom["previous"] > 0 and mom["delta_pct"] is not None:
        direction = "more" if mom["delta"] > 0 else "less"
        sentences.append(
            f"That's {abs(mom['delta_pct']):.1f}% {direction} than {mom['previous_month']}."
        )

    if summary["by_category"]:
        top = summary["by_category"][0]
        sentences.append(f"{top['category']} was your top category at ₹{top['total']:,.2f}.")

    budget = _budget(session, user_id)
    if budget:
        pct = (totals["expenses"] / budget * 100.0) if budget else 0.0
        if pct > 100:
            sentences.append(f"You're {pct - 100:.0f}% over your monthly budget.")
        else:
            sentences.append(f"You've used {pct:.0f}% of your monthly budget.")

    return " ".join(sentences)


def dashboard_payload(session: Session, user_id, month: str) -> dict:
    """Everything the dashboard insights card needs in one call."""
    summary = monthly_summary(session, user_id, month)
    mom = month_over_month(session, user_id, month)
    trend_data = trend(session, user_id, month)
    budget_limit = _budget(session, user_id)
    budget_used = summary["totals"]["expenses"]
    budget_pct = (budget_used / budget_limit * 100.0) if budget_limit else None
    return {
        "month": month,
        "summary_text": plain_language_summary(session, user_id, month),
        "totals": summary["totals"],
        "top_categories": summary["by_category"][:5],
        "month_over_month": mom,
        "trend": trend_data,
        "anomalies": anomalies(trend_data),
        "budget": {
            "limit": budget_limit,
            "used": budget_used,
            "pct": budget_pct,
            "over": bool(budget_pct is not None and budget_pct > 100),
        },
    }
