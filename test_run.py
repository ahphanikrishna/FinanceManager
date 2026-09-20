import re
import uuid

import unittest
from run import app

from app.database import Base, engine, ensure_user_columns
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
        ensure_user_columns(engine)


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


class TestProfileSettings(LoggedInTestCase):
    """Profile email is the login identifier (besides username)."""

    def test_profile_tab_renders(self):
        response = self.client.get("/settings?tab=profile")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-settings-tab="profile"', body)
        self.assertIn('id="profile-email"', body)

    def test_save_profile_email_enables_email_login(self):
        email = f"profile_{uuid.uuid4().hex[:8]}@example.com"
        response = self.client.post("/settings/profile", data={"email": email}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        session = DatabaseRepository().get_session()
        try:
            user = session.get(User, self.user_id)
            self.assertEqual(user.email, email)
        finally:
            session.close()
        self.client.get("/logout")
        response = self.client.post(
            "/login",
            data={"username": email, "password": "SmokeTest123!"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302, "login by saved profile email should succeed")


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
        response = self.client.get(f"/api/v1/insights/trends?user_id={self.user_id}&month={self.cur_month}")
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


class TestGmailSync(LoggedInTestCase):
    """Smoke tests for the Gmail sync settings flow (no live credentials)."""

    def setUp(self):
        super().setUp()
        session = DatabaseRepository().get_session()
        try:
            self.member = Member(name="SMOKE MEMBER", user_id=self.user_id)
            self.account = Account(account_name="Smoke SBI", account_type="Savings", user_id=self.user_id)
            session.add(self.member)
            session.add(self.account)
            session.commit()
            self.account_id = self.account.id
            self.member_id = self.member.id
        finally:
            session.close()

    def test_gmail_tab_renders(self):
        body = self.client.get("/settings?tab=gmail").get_data(as_text=True)
        self.assertIn("Gmail Sync", body)
        self.assertIn("not configured", body)

    def test_save_gmail_address(self):
        address = f"{self.username}@example.com"
        response = self.client.post("/settings/gmail", data={"gmail_address": address})
        self.assertEqual(response.status_code, 302)
        session = DatabaseRepository().get_session()
        try:
            user = session.get(User, self.user_id)
            self.assertEqual(user.gmail_address, address)
        finally:
            session.close()

    def test_fetch_without_credentials_reports_not_configured(self):
        response = self.client.post(
            "/settings/gmail/fetch",
            data={
                "month": "2024-01",
                "account_id": str(self.account_id),
                "member_id": str(self.member_id),
            },
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertIn("Gmail sync stopped", body)
        self.assertIn("No Google credentials configured", body)

    def test_guess_parsers_mapping(self):
        from app.services.statement_import import guess_parsers

        self.assertTrue(any("sbi" in pair[0] for pair in guess_parsers("SBI_Passbook_Jan.xlsx")))
        self.assertTrue(any("hdfc_cc" in pair[0] for pair in guess_parsers("HDFC_CC_Dec.pdf")))
        self.assertTrue(guess_parsers("Unknown_Bank_Statement.xlsx"))
        self.assertEqual(guess_parsers("notes.txt"), [])


class TestDisplayConventions(LoggedInTestCase):
    """Amounts render with comma grouping; views start on the previous month."""

    def setUp(self):
        super().setUp()
        from datetime import date, timedelta

        today = date.today()
        self.cur_month = today.strftime("%Y-%m")
        prev_day = today.replace(day=1) - timedelta(days=1)
        self.prev_month = prev_day.strftime("%Y-%m")

        session = DatabaseRepository().get_session()
        try:
            session.add(Transaction(
                date=today.replace(day=15),
                member="SMOKE MEMBER",
                account="Smoke SBI",
                account_type="Savings",
                description="Large transfer display check",
                type="Expenditure",
                amount=-1234567.5,
                category="Transfer",
                subcategory="Internal",
                fill_type="Manual",
                comments="",
                user_id=self.user_id,
            ))
            session.commit()
        finally:
            session.close()

    def test_transactions_page_comma_groups_amounts(self):
        body = self.client.get(f"/transactions?month={self.cur_month}").get_data(as_text=True)
        self.assertIn("\u20b9-1,234,567.50", body)  # ₹-1,234,567.50

    def test_dashboard_comma_groups_amounts(self):
        body = self.client.get(f"/dashboard?month={self.cur_month}").get_data(as_text=True)
        self.assertIn("1,234,567.50", body)

    def test_transactions_defaults_to_previous_month(self):
        body = self.client.get("/transactions").get_data(as_text=True)
        self.assertIn(f'value="{self.prev_month}"', body)

    def test_dashboard_defaults_to_previous_month(self):
        body = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn(f'value="{self.prev_month}"', body)

    def test_gmail_fetch_defaults_to_previous_month(self):
        body = self.client.get("/settings?tab=gmail").get_data(as_text=True)
        self.assertIn(f'value="{self.prev_month}"', body)


class TestFinGrid(LoggedInTestCase):
    """The dashboard 2x2 grid: grouped, sorted, populated for every type."""

    def setUp(self):
        super().setUp()
        from datetime import date

        today = date.today()
        self.cur_month = today.strftime("%Y-%m")
        day = today.replace(day=15)
        self.seed = [
            ("Expenditure", "Transport", "Refuel", "Petrol", -450.00),
            ("Expenditure", "Groceries", "Online", "Grocery app order", -250.50),
            ("Expenditure", "Groceries", "Fresh", "Market purchase", -120.00),
            ("Expenditure", "Groceries", "Online", "Second grocery order", -80.25),
            ("Income", "Salary", "Monthly", "Monthly salary", 50000.00),
            ("Investment", "Assets", "Mutual Fund", "MF SIP", -3000.00),
            ("Investment", "Assets", "Gold", "Gold purchase", -2000.00),
            ("Investment", "Fixed Deposit", "", "FD booking", -2500.00),
            ("Transfer", "Transfers", "From Others", "Inbound", 15000.00),
            ("Transfer", "Transfers", "To Others", "Outbound", -10000.00),
        ]
        session = DatabaseRepository().get_session()
        try:
            for tx_type, category, subcategory, description, amount in self.seed:
                session.add(Transaction(
                    date=day,
                    member="SMOKE MEMBER",
                    account="Smoke SBI",
                    account_type="Savings",
                    description=description,
                    type=tx_type,
                    amount=amount,
                    category=category,
                    subcategory=subcategory,
                    fill_type="Manual",
                    comments="",
                    user_id=self.user_id,
                ))
            session.commit()
        finally:
            session.close()

    def _body(self):
        return self.client.get(f"/dashboard?month={self.cur_month}").get_data(as_text=True)

    def _card_html(self, body, fin_type):
        match = re.search(
            f'<section class="card fin-card" data-fin-type="{fin_type}".*?</section>',
            body, re.S,
        )
        self.assertIsNotNone(match, f"missing {fin_type} card")
        return match.group(0)

    def test_investment_and_transfer_cards_render_items(self):
        # Regression: investments/transfers used to show totals but blank lists.
        body = self._body()
        for fin_type, marker in (
            ("Investment", 'data-amount="3000.00"'),
            ("Transfer", 'data-amount="15000.00"'),
            ("Expenditure", 'data-amount="450.00"'),
            ("Income", 'data-amount="50000.00"'),
        ):
            card = self._card_html(body, fin_type)
            self.assertIn("fin-item-check", card, f"{fin_type} card has no selectable items")
            self.assertIn(marker, card)

    def test_grouped_hierarchy_and_polish_elements(self):
        body = self._body()
        self.assertNotIn("Monthly Balances Overview", body)
        self.assertNotIn("fin-category-select", body)
        for fin_type in ("Expenditure", "Income", "Investment", "Transfer"):
            self.assertIn(f'data-fin-type="{fin_type}"', body)
        # Grouped category -> subcategory hierarchy with badges and progress bars.
        for marker in ("fin-groups", "fin-group-toggle", "fin-subs", "fin-sub-toggle",
                       "fin-badge", "fin-group-bar", "fin-collapse-toggle",
                       "fin-sub-collapse", "fin-item-desc",
                       'data-fin-action="all"', 'data-fin-action="none"'):
            self.assertIn(marker, body)
        # One collapse toggle per category group and per named subcategory.
        exp = self._card_html(body, "Expenditure")
        self.assertEqual(
            exp.count('class="fin-collapse-toggle"'),
            exp.count('class="fin-group collapsed"'),
        )
        self.assertEqual(
            exp.count('class="fin-sub-collapse"'),
            exp.count('class="fin-sub-header"'),
        )
        # Final line items show the transaction description.
        self.assertIn("Market purchase", exp)
        # Subcategory with an empty name (Fixed Deposit) still renders its items.
        fd_card = self._card_html(body, "Investment")
        self.assertIn("Fixed Deposit", fd_card)
        self.assertIn('data-amount="2500.00"', fd_card)

    def test_descending_sort_orders(self):
        body = self._body()
        exp = self._card_html(body, "Expenditure")
        # Categories: Groceries (450.75) before Transport (450.00).
        self.assertLess(exp.index(">Groceries<"), exp.index(">Transport<"))
        # Subcategories: Online (330.75) before Fresh (120.00).
        self.assertLess(exp.index(">Online<"), exp.index(">Fresh<"))
        # Line items: 250.50 before 80.25 inside Online.
        self.assertLess(exp.index('data-amount="250.50"'), exp.index('data-amount="80.25"'))
        inv = self._card_html(body, "Investment")
        # Categories: Assets (5000) before Fixed Deposit (2500); subs: Mutual Fund before Gold.
        self.assertLess(inv.index(">Assets<"), inv.index(">Fixed Deposit<"))
        self.assertLess(inv.index(">Mutual Fund<"), inv.index(">Gold<"))
        trf = self._card_html(body, "Transfer")
        # Signed sort: positive From Others before negative To Others.
        self.assertLess(trf.index(">From Others<"), trf.index(">To Others<"))

    def test_group_and_card_totals_render(self):
        body = self._body()
        exp = self._card_html(body, "Expenditure")
        self.assertIn("₹450.75", exp)  # Groceries group total
        self.assertIn("₹330.75", exp)  # Online subcategory total
        # Metric cards summarize absolute totals, matching the grid cards.
        self.assertIn("₹900.75", body)   # Expenditure 900.75
        self.assertIn("₹7,500.00", body)  # Investments 7,500
        self.assertIn("₹5,000.00", body)  # Transfers net 15,000 - 10,000

    def test_transfer_card_keeps_signs_and_nets_out(self):
        body = self._body()
        trf = self._card_html(body, "Transfer")
        # To others is negative, from others is positive.
        self.assertIn('data-amount="-10000.00"', trf)
        self.assertIn('data-amount="15000.00"', trf)
        self.assertIn("₹-10,000.00", trf)  # To Others subcategory total
        self.assertIn("₹15,000.00", trf)   # From Others subcategory total
        # Grouped, they mostly cancel out: category total is the net.
        self.assertIn("₹5,000.00", trf)

    def test_grid_carries_trend_payload_and_scripts(self):
        body = self._body()
        self.assertIn('id="fin-grid-data"', body)
        self.assertIn('"labels"', body)
        self.assertIn('"All"', body)
        self.assertIn('"groups"', body)
        self.assertIn('chart.umd', body)
        self.assertIn('fin-grid.js', body)

    def test_dashboard_tabs(self):
        body = self._body()
        self.assertIn('class="dash-tabs"', body)
        self.assertIn('role="tab"', body)
        for name in ("insights", "grid", "graphs"):
            self.assertIn(f'data-dash-tab="{name}"', body)
            self.assertIn(f'data-dash-panel="{name}"', body)

    def test_graph_dropdowns_offer_category_series(self):
        body = self._body()
        self.assertEqual(body.count('class="fin-chart-select"'), 4)
        exp_chart = re.search(
            r'<div class="fin-chart" data-fin-type="Expenditure">.*?</select>', body, re.S
        )
        self.assertIsNotNone(exp_chart)
        self.assertIn('<option value="All" selected>All</option>', exp_chart.group(0))
        self.assertIn('<option value="Groceries">', exp_chart.group(0))
        self.assertIn('<option value="Groceries|Online">', exp_chart.group(0))
        self.assertIn('<option value="Groceries|Fresh">', exp_chart.group(0))
        self.assertIn('<option value="Transport">', exp_chart.group(0))
        trf_chart = re.search(
            r'<div class="fin-chart" data-fin-type="Transfer">.*?</select>', body, re.S
        )
        self.assertIn('<option value="Transfers|To Others">', trf_chart.group(0))
        self.assertIn('<option value="Transfers|From Others">', trf_chart.group(0))

    def test_charts_separate_section_and_collapsed_defaults(self):
        body = self._body()
        # Categories and subcategories render collapsed by default.
        exp = self._card_html(body, "Expenditure")
        self.assertEqual(
            exp.count('class="fin-group collapsed"'),
            exp.count('class="fin-group-header"'),
        )
        self.assertEqual(
            exp.count('class="fin-sub collapsed"'),
            exp.count('class="fin-sub-header"'),
        )
        self.assertIn('aria-expanded="false"', exp)
        # Charts live in their own section, not inside the 2x2 cards.
        self.assertIn('fin-chart-grid', body)
        self.assertEqual(body.count('<canvas'), 4)
        for fin_type in ("Expenditure", "Income", "Investment", "Transfer"):
            self.assertNotIn('<canvas', self._card_html(body, fin_type))
        charts = re.search(r'<section class="card fin-charts".*?</section>', body, re.S)
        self.assertIsNotNone(charts)
        for fin_type in ("Expenditure", "Income", "Investment", "Transfer"):
            self.assertIn(f'data-fin-type="{fin_type}"', charts.group(0))


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
