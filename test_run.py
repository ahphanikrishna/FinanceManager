import unittest
from run import app

# Mocking the DatabaseRepository and app context is necessary for isolated unit tests.

class TestRunApp(unittest.TestCase):

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

if __name__ == '__main__':
    unittest.main()