import uuid

import unittest
from run import app

from app.database import Base, engine
from app.models import Account, Category, Member, Onboarding, User
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
        for model in (Category, Account, Member, Onboarding):
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
