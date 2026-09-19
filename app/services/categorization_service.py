"""Historical category auto-classification.

Suggests categories/subcategories for a transaction based on the
user's own categorized history (member/account/type context +
description keyword overlap), with a relative confidence score and
support count. Auto-apply only fills 'Uncategorized' transactions
whose top suggestion clears a confidence + minimum support gate,
and every suggestion is overridable in the UI.
"""
import re
from collections import Counter

from sqlalchemy.orm import Session

from ..models import Transaction

MINIMUM_SUPPORT = 3
DEFAULT_THRESHOLD = 0.6


def _tokenize(text) -> set:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 1}


def _load_candidates(session: Session, user_id, member=None, account=None, tx_type=None, limit=5000):
    """Aggregate the user's categorized history into candidate buckets."""
    query = (
        session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.category != "Uncategorized",
        )
    )
    if member:
        query = query.filter(Transaction.member == member)
    if account:
        query = query.filter(Transaction.account == account)
    if tx_type:
        query = query.filter(Transaction.type == tx_type)
    rows = query.order_by(Transaction.date.desc()).limit(limit).all()

    candidates = {}
    for tx in rows:
        category = (tx.category or "Uncategorized").strip()
        if category == "Uncategorized":
            continue
        subcategory = (tx.subcategory or category).strip()
        key = (category, subcategory)
        entry = candidates.setdefault(key, {"count": 0, "tokens": Counter()})
        entry["count"] += 1
        entry["tokens"].update(_tokenize(tx.description))
    return candidates


def score_candidates(candidates, description):
    """Score pre-loaded candidate buckets against a description."""
    description_tokens = _tokenize(description)
    scored = []
    for (category, subcategory), entry in candidates.items():
        name_tokens = _tokenize(category) | _tokenize(subcategory)
        overlap = len(description_tokens & (name_tokens | set(entry["tokens"])))
        score = entry["count"] * 2.0 + overlap * 3.0
        scored.append({
            "category": category,
            "subcategory": subcategory,
            "score": score,
            "support": entry["count"],
            "matched_terms": sorted(description_tokens & (name_tokens | set(entry["tokens"]))),
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    top = scored[:10]
    max_score = top[0]["score"] if top else 0.0
    for item in top:
        item["confidence"] = round(item["score"] / max_score, 3) if max_score else 0.0
        del item["score"]
    return top


def suggest_categories(session: Session, user_id, description="", member=None, account=None, tx_type=None):
    """Return ranked suggestions: [{category, subcategory, confidence, support}]."""
    candidates = _load_candidates(session, user_id, member=member, account=account, tx_type=tx_type)
    return score_candidates(candidates, description)


def auto_categorize(session: Session, user_id, threshold=DEFAULT_THRESHOLD, limit=200, month=None):
    """Fill uncategorized transactions using confident historical matches.

    Returns a report: {"considered", "updated", "skipped", "updated_rows"}.
    """
    query = session.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.category == "Uncategorized",
    )
    if month:
        from datetime import datetime

        month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        query = query.filter(Transaction.date >= month_start)
    pending = query.order_by(Transaction.date.desc()).limit(limit).all()

    candidate_cache = {}
    updated = 0
    updated_rows = []
    for transaction in pending:
        context = (transaction.member, transaction.account, transaction.type)
        if context not in candidate_cache:
            candidate_cache[context] = _load_candidates(
                session, user_id,
                member=context[0], account=context[1], tx_type=context[2],
            )
        top_suggestion = score_candidates(candidate_cache[context], transaction.description)
        if not top_suggestion:
            continue
        top = top_suggestion[0]
        if top["confidence"] >= threshold and top["support"] >= MINIMUM_SUPPORT:
            transaction.category = top["category"]
            transaction.subcategory = top["subcategory"]
            if not (transaction.comments or "").strip():
                transaction.comments = "Auto-categorized"
            updated += 1
            updated_rows.append({
                "id": transaction.id,
                "category": top["category"],
                "subcategory": top["subcategory"],
                "confidence": top["confidence"],
            })
    if updated:
        session.commit()
    return {
        "considered": len(pending),
        "updated": updated,
        "skipped": len(pending) - updated,
        "updated_rows": updated_rows,
    }
