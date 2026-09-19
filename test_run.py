import uuid

import unittest
from run import app

from app.database import Base, engine

# Mocking the DatabaseRepository and app context is necessary for isolated unit tests.

class BaseTestCase(unittest.TestCase):
    """Shared harness: make sure the schema exists for the test database."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)


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


class TestOnboardingFlow(BaseTestCase):
    """Smoke tests for the first-run onboarding wizard."""

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.username = f"smoke_user_{uuid.uuid4().hex[:10]}"

        response = self.client.post(
            "/register",
            data={
                "username": self.username,
                "email": f"{self.username}@example.com",
                "password": "SmokeTest123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/onboarding", response.headers.get("Location", ""))

        from app.models import User
        from app.repository import DatabaseRepository

        session = DatabaseRepository().get_session()
        try:
            self.user = session.query(User).filter_by(username=self.username).first()
            self.assertIsNotNone(self.user)
            self.user_id = self.user.id
        finally:
            session.close()

    def tearDown(self):
        from app.models import Account, Category, Member, Onboarding, User
        from app.repository import DatabaseRepository

        session = DatabaseRepository().get_session()
        try:
            for model in (Category, Account, Member, Onboarding):
                for row in session.query(model).filter(model.user_id == self.user_id).all():
                    session.delete(row)
            user = session.get(User, self.user_id)
            if user is not None:
                session.delete(user)
            session.commit()
        finally:
            session.close()
        self.app.config['TESTING'] = False

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
