"""Monthly spend insights service.

Computes spend summaries, category breakdowns, month-over-month
comparisons, short-term trends, and plain-language summaries from
the user's historical transactions. Pure reads, scoped per user.
"""
import zlib
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import Onboarding, Transaction

TREND_MONTHS = 6

_BADGE_PALETTE = (
    ("#eef2ff", "#4338ca"),
    ("#ecfdf5", "#047857"),
    ("#fff7ed", "#c2410c"),
    ("#fdf2f8", "#be185d"),
    ("#eff6ff", "#1d4ed8"),
    ("#f0fdf4", "#15803d"),
    ("#fefce8", "#a16207"),
    ("#f5f3ff", "#6d28d9"),
    ("#ecfeff", "#0e7490"),
    ("#f1f5f9", "#334155"),
)

FIN_GRID_TYPES = (
    ("Expenditure", "Expenditure"),
    ("Income", "Income"),
    ("Investment", "Investments"),
    ("Transfer", "Transfers"),
)


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


def _badge_for(name: str) -> dict:
    """Stable soft color pair (background, foreground) per category name."""
    index = zlib.crc32(name.encode("utf-8")) % len(_BADGE_PALETTE)
    background, foreground = _BADGE_PALETTE[index]
    return {"bg": background, "fg": foreground}


def _trend_labels(end_month: str, months: int = TREND_MONTHS) -> list:
    """Month strings (YYYY-MM), oldest first, ending at end_month."""
    labels = []
    current = end_month
    for _ in range(months):
        labels.insert(0, current)
        current = previous_month(current)
    return labels


def financial_grid_payload(session: Session, user_id, month: str) -> dict:
    """Payload for the dashboard 2x2 financial grid.

    For each transaction type the payload carries the selected month's line
    items, the categories/subcategories present in that month, and a
    ``TREND_MONTHS``-month total series keyed by ``"All"``,
    ``"<Category>"`` and ``"<Category>|<Subcategory>"``.
    """
    user_id = int(user_id)
    start, end = _month_bounds(month)
    labels = _trend_labels(month)
    window_start = date(int(labels[0][:4]), int(labels[0][5:7]), 1)
    transactions = _transactions_between(session, user_id, window_start, end)

    type_key_by_name = {key.strip().lower(): key for key, _ in FIN_GRID_TYPES}
    bucket_totals = {}
    items_by_type = {key: [] for key, _ in FIN_GRID_TYPES}

    for tx in transactions:
        type_key = type_key_by_name.get((tx.type or "").strip().lower())
        if not type_key or not tx.date:
            continue
        category = (tx.category or "").strip() or "Uncategorized"
        subcategory = (tx.subcategory or "").strip()
        # Transfers keep their sign (to others = negative, from others =
        # positive) so grouped transfers net out; other types are magnitude.
        amount = float(tx.amount or 0.0) if type_key == "Transfer" else abs(float(tx.amount or 0.0))
        month_str = tx.date.strftime("%Y-%m")
        bucket_totals[(type_key, category, subcategory, month_str)] = (
            bucket_totals.get((type_key, category, subcategory, month_str), 0.0) + amount
        )
        if month_str == month:
            items_by_type[type_key].append({
                "id": tx.id,
                "date": tx.date.isoformat(),
                "description": tx.description or "",
                "category": category,
                "subcategory": subcategory,
                "amount": round(amount, 2),
            })

    for type_key in items_by_type:
        items_by_type[type_key].sort(key=lambda item: -item["amount"])

    cards = []
    for type_key, label in FIN_GRID_TYPES:
        category_totals = {}
        category_subs = {}
        for (t, category, subcategory, month_str), total in bucket_totals.items():
            if t != type_key or month_str != month:
                continue
            category_totals[category] = category_totals.get(category, 0.0) + total
            category_subs.setdefault(category, {})
            category_subs[category][subcategory] = (
                category_subs[category].get(subcategory, 0.0) + total
            )

        categories = []
        for category in sorted(category_totals, key=lambda name: -category_totals[name]):
            sub_totals = category_subs.get(category, {})
            categories.append({
                "name": category,
                "subcategories": [
                    {"name": name, "total": round(total, 2)}
                    for name, total in sorted(sub_totals.items(), key=lambda item: -item[1])
                ],
            })

        def series_for(category=None, subcategory=None):
            series = []
            for label_month in labels:
                total = 0.0
                for (t, category_key, sub_key, month_str), value in bucket_totals.items():
                    if t != type_key or month_str != label_month:
                        continue
                    if category is not None and category_key != category:
                        continue
                    if subcategory is not None and sub_key != subcategory:
                        continue
                    total += value
                series.append(round(total, 2))
            return series

        trend = {"All": series_for()}
        for category in category_totals:
            trend[category] = series_for(category=category)
            for subcategory in category_subs.get(category, {}):
                trend[f"{category}|{subcategory}"] = series_for(category=category, subcategory=subcategory)

        card_total = sum(category_totals.values())
        # Progress bars use magnitude shares so signed nets (transfers) still
        # render a sensible bar width.
        category_magnitude = {}
        for item in items_by_type[type_key]:
            category_magnitude[item["category"]] = (
                category_magnitude.get(item["category"], 0.0) + abs(item["amount"])
            )
        card_magnitude = sum(category_magnitude.values())
        groups = []
        for category in sorted(category_totals, key=lambda name: -category_totals[name]):
            sub_totals = category_subs.get(category, {})
            subs = []
            for sub_name in sorted(sub_totals, key=lambda name: -sub_totals[name]):
                sub_items = [
                    item
                    for item in items_by_type[type_key]
                    if item["category"] == category and item["subcategory"] == sub_name
                ]
                subs.append({
                    "name": sub_name,
                    "total": round(sub_totals[sub_name], 2),
                    "items": sub_items,
                })
            groups.append({
                "name": category,
                "total": round(category_totals[category], 2),
                "share": round(category_magnitude.get(category, 0.0) / card_magnitude * 100, 1) if card_magnitude else 0.0,
                "badge": _badge_for(category),
                "subcategories": subs,
            })

        cards.append({
            "type": type_key,
            "label": label,
            "total": round(card_total, 2),
            "items": items_by_type[type_key],
            "categories": categories,
            "groups": groups,
            "trend": trend,
        })

    return {"month": month, "labels": labels, "cards": cards}


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
