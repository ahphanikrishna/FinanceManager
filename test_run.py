import uuid

import unittest
from run import app

from app.database import Base, engine
from app.models import Account, Category, Member, Onboarding, Transaction, User
from app.repository import DatabaseRepository

# Mocking the DatabaseRepository and app context is necessary for isolated unit tests.


def register_test_user(client, prefix="smoke_user"):
    """Register a fresh user through the real registration flow."""
    username = f"{prefix}_{uuid.uuid4().hex[:10]}"
    response = client.post(
        "/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "SmokeTest123!",
        },
    )
    assert response.status_code == 302, response.get_data(as_text=True)
    session = DatabaseRepository().get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
    finally:
        session.close()
    assert user is not None
    return username, user.id


def cleanup_test_user(user_id):
    session = DatabaseRepository().get_session()
    try:
        for model in (Transaction, Category, Account, Member, Onboarding):
            for row in session.query(model).filter(model.user_id == user_id).all():
                session.delete(row)
        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)
        session.commit()
    finally:
        session.close()


class BaseTestCase(unittest.TestCase):
    """Shared harness: make sure the schema exists for the test database."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)


class LoggedInTestCase(BaseTestCase):
    """Base class for tests that need an authenticated smoke user."""

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.username, self.user_id = register_test_user(self.client)

    def tearDown(self):
        cleanup_test_user(self.user_id)
        self.app.config['TESTING'] = False


class TestRunApp(BaseTestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.config['TESTING'] = False

    def test_index_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Balance Management', response.get_data(as_text=True))

    def test_login_page_renders(self):
        response = self.client.get('/login')
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="username"', body)
        self.assertIn('action="/login"', body)


class TestPageRendering(LoggedInTestCase):
    """Core pages must render for an authenticated user."""

    def test_core_pages_render(self):
        for path in ("/dashboard", "/transactions", "/settings", "/onboarding"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_accounts_redirects_to_settings(self):
        response = self.client.get("/accounts")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings", response.headers.get("Location", ""))


class TestInsights(LoggedInTestCase):
    """Smoke tests for monthly spend insights (service -> API + dashboard)."""

    def _seed(self, day: int, tx_type: str, amount: float, category: str, month_date):
        session = DatabaseRepository().get_session()
        try:
            session.add(Transaction(
                date=month_date.replace(day=day),
                member="SMOKE MEMBER",
                account="Smoke SBI",
                account_type="Savings",
                description=f"{category} test entry",
                type=tx_type,
                amount=-abs(amount) if tx_type in ("Expenditure", "Investment") else abs(amount),
                category=category,
                subcategory=category,
                fill_type="Manual",
                comments="",
                user_id=self.user_id,
            ))
            session.commit()
        finally:
            session.close()

    def setUp(self):
        super().setUp()
        from datetime import date, timedelta

        today = date.today()
        self.cur_month = today.strftime("%Y-%m")
        prev_day = today.replace(day=1) - timedelta(days=1)
        prev2_day = prev_day.replace(day=1) - timedelta(days=1)
        self.prev_month = prev_day.strftime("%Y-%m")

        self._seed(5, "Expenditure", 100, "Groceries", today)
        self._seed(6, "Expenditure", 500, "Rent", today)
        self._seed(1, "Income", 2000, "Salary", today)
        self._seed(5, "Expenditure", 300, "Food", prev_day)
        self._seed(5, "Expenditure", 250, "Food", prev2_day)

    def test_summary_api(self):
        response = self.client.get(f"/api/v1/insights/summary?month={self.cur_month}&user_id={self.user_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertAlmostEqual(data["totals"]["expenses"], 600.0)
        self.assertAlmostEqual(data["totals"]["income"], 2000.0)
        self.assertEqual(data["by_category"][0]["category"], "Rent")
        self.assertAlmostEqual(data["month_over_month"]["delta_pct"], 100.0)
        self.assertIn("top category", data["summary_text"])

    def test_trends_api(self):
        response = self.client.get(f"/api/v1/insights/trends?user_id={self.user_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["series"]), 6)
        total = sum(point["expenses"] for point in data["series"])
        self.assertAlmostEqual(total, 1150.0)

    def test_dashboard_renders_insights(self):
        body = self.client.get(f"/dashboard?month={self.cur_month}").get_data(as_text=True)
        self.assertIn("Insights", body)
        self.assertIn("top category", body)
        self.assertIn("Spending is up", body)


class TestCategorization(LoggedInTestCase):
    """Smoke tests for historical auto-classification of transactions."""

    def _seed_tx(self, day, tx_type, amount, category, subcategory, description):
        from datetime import date

        session = DatabaseRepository().get_session()
        today = date.today()
        try:
            session.add(Transaction(
                date=today.replace(day=day),
                member="SMOKE MEMBER",
                account="Smoke SBI",
                account_type="Savings",
                description=description,
                type=tx_type,
                amount=-abs(amount),
                category=category,
                subcategory=subcategory,
                fill_type="Manual",
                comments="",
                user_id=self.user_id,
            ))
            session.commit()
        finally:
            session.close()

    def setUp(self):
        super().setUp()
        self._seed_tx(3, "Expenditure", 111, "Groceries", "Online", "BigBasket order")
        self._seed_tx(4, "Expenditure", 112, "Groceries", "Online", "BigBasket order")
        self._seed_tx(5, "Expenditure", 113, "Groceries", "Online", "BigBasket order")
        self._seed_tx(6, "Expenditure", 114, "Groceries", "Online", "BigBasket order")
        self._seed_tx(10, "Expenditure", 31, "Software", "SaaS", "Office 365 subscription")
        self._seed_tx(11, "Expenditure", 32, "Software", "SaaS", "Office 365 subscription")
        self._seed_tx(12, "Expenditure", 33, "Software", "SaaS", "Office 365 subscription")
        self._seed_tx(14, "Expenditure", 45, "Uncategorized", "Uncategorized", "BigBasket monthly order")

    def test_suggestion_api(self):
        payload = {
            "user_id": self.user_id,
            "description": "BigBasket monthly order",
            "member": "SMOKE MEMBER",
            "account": "Smoke SBI",
            "type": "Expenditure",
        }
        response = self.client.post("/api/v1/suggestions/categorize", json=payload)
        self.assertEqual(response.status_code, 200)
        top = response.get_json()["suggestions"][0]
        self.assertEqual(top["category"], "Groceries")
        self.assertEqual(top["subcategory"], "Online")
        self.assertEqual(top["support"], 4)
        self.assertEqual(top["confidence"], 1.0)

    def test_auto_categorize_fills_uncategorized(self):
        session = DatabaseRepository().get_session()
        try:
            pending = session.query(Transaction).filter(
                Transaction.user_id == self.user_id,
                Transaction.category == "Uncategorized",
            ).first()
            pending_id = pending.id
        finally:
            session.close()

        response = self.client.post("/api/v1/suggestions/apply", json={"user_id": self.user_id})
        self.assertEqual(response.status_code, 200)
        report = response.get_json()
        self.assertEqual(report["considered"], 1)
        self.assertEqual(report["updated"], 1)

        session = DatabaseRepository().get_session()
        try:
            updated = session.get(Transaction, pending_id)
            self.assertEqual(updated.category, "Groceries")
            self.assertEqual(updated.subcategory, "Online")
        finally:
            session.close()

    def test_transactions_page_has_suggestion_ui(self):
        body = self.client.get("/transactions").get_data(as_text=True)
        self.assertIn("category-suggestion-hint", body)
        self.assertIn("Auto-categorize uncategorized", body)


class TestOnboardingFlow(LoggedInTestCase):
    """Smoke tests for the first-run onboarding wizard."""

    def test_wizard_happy_path(self):
        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Your profile", body)

        self.assertEqual(self.client.post("/onboarding/step").status_code, 302)

        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Add your members", body)

        response = self.client.post("/onboarding/members", data={"name": "SMOKE MEMBER"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post("/onboarding/step").status_code, 302)

        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Add your accounts", body)

        response = self.client.post(
            "/onboarding/accounts",
            data={"account_name": "Smoke SBI", "account_type": "Savings"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post("/onboarding/step").status_code, 302)

        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Add your categories", body)

        response = self.client.post(
            "/onboarding/categories",
            data={"Category": "Groceries", "subcategory": "Food", "type": "Expenditure"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post("/onboarding/step").status_code, 302)

        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Monthly budget", body)

        response = self.client.post("/onboarding/complete", data={"monthly_budget": "5000"})
        self.assertEqual(response.status_code, 302)

        body = self.client.get("/onboarding").get_data(as_text=True)
        self.assertIn("Setup complete", body)

    def test_member_required_before_advance(self):
        self.client.post("/onboarding/step")  # profile -> members
        response = self.client.post("/onboarding/step", follow_redirects=True)
        self.assertIn("Add at least one member to continue.", response.get_data(as_text=True))

    def test_dashboard_shows_setup_banner_until_complete(self):
        body = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Continue setup", body)

        self.client.post("/onboarding/members", data={"name": "SMOKE MEMBER"})
        self.client.post("/onboarding/accounts", data={"account_name": "Smoke SBI", "account_type": "Savings"})
        self.client.post("/onboarding/categories", data={"Category": "Groceries", "subcategory": "Food", "type": "Expenditure"})
        self.client.post("/onboarding/complete")

        body = self.client.get("/dashboard").get_data(as_text=True)
        self.assertNotIn("Continue setup", body)


if __name__ == '__main__':
    unittest.main()
