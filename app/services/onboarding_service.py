"""Service layer for first-run onboarding progress.

Keeps wizard state rules out of the view layer so the dashboard,
auth flow, and tests can share the same completion logic.
"""
from sqlalchemy.orm import Session

from ..models import Account, Category, Member, Onboarding

STEP_PROFILE = 1
STEP_MEMBERS = 2
STEP_ACCOUNTS = 3
STEP_CATEGORIES = 4
STEP_BUDGET = 5
TOTAL_STEPS = 5

STEP_LABELS = {
    STEP_PROFILE: "Profile",
    STEP_MEMBERS: "Members",
    STEP_ACCOUNTS: "Accounts",
    STEP_CATEGORIES: "Categories",
    STEP_BUDGET: "Budget",
}


def get_progress(session: Session, user_id: int):
    """Return the user's onboarding row, or None."""
    return session.query(Onboarding).filter(Onboarding.user_id == user_id).first()


def ensure_progress(session: Session, user_id: int) -> Onboarding:
    """Return the user's onboarding row, creating it on first access."""
    progress = get_progress(session, user_id)
    if progress is None:
        progress = Onboarding(user_id=user_id, current_step=0)
        session.add(progress)
        session.commit()
    return progress


def is_complete(progress) -> bool:
    """Completion state is explicit: a completed_at timestamp."""
    return bool(progress is not None and progress.completed_at is not None)


def current_step(progress) -> int:
    """The wizard step the user is currently viewing (1..5)."""
    if progress is None:
        return STEP_PROFILE
    completed = progress.current_step or 0
    if is_complete(progress):
        return TOTAL_STEPS
    return min(completed + 1, TOTAL_STEPS)


def entity_counts(session: Session, user_id: int) -> dict:
    """How many setup entities the user has so far."""
    return {
        "members": session.query(Member).filter(Member.user_id == user_id).count(),
        "accounts": session.query(Account).filter(Account.user_id == user_id).count(),
        "categories": session.query(Category).filter(Category.user_id == user_id).count(),
    }


def can_complete(session: Session, user_id: int):
    """Gate the final step: the wizard requires at least one of each entity."""
    counts = entity_counts(session, user_id)
    missing = [label for label, key in (("member", "members"), ("account", "accounts"), ("category", "categories")) if counts[key] == 0]
    if missing:
        return False, "Add at least one " + " and one ".join(missing) + " to complete setup."
    return True, ""
