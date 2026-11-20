import unittest
from fastapi.testclient import TestClient
from app import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_dashboard_and_health(self):
        home=self.client.get('/')
        self.assertEqual(home.status_code,200)
        self.assertIn('Every millisecond',home.text)
        self.assertEqual(self.client.get('/api/health').json()['status'],'ok')
        self.assertIn('javascript',self.client.get('/static/app.js').headers['content-type'])

    def test_valid_run(self):
        response=self.client.post('/api/start',json={'mode':'blocking','settings':{'target_speed':7,'network_rtt_ms':10}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['mode'],'blocking')
        moved=self.client.post('/api/advance',json={'steps':100})
        self.assertEqual(moved.status_code,200)
        self.assertGreater(moved.json()['robot']['x'],8)

    def test_comparison_same_settings(self):
        response=self.client.post('/api/compare',json={'mode':'async','settings':{'network_rtt_ms':50}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['blocking']['result'],'collision')
        self.assertEqual(response.json()['async']['result'],'safe_stop')

    def test_invalid_configuration_and_step_limits(self):
        for body in ({'settings':{'braking':-1}},{'mode':'invalid'},{'settings':{'hacked':'x'}}):
            self.assertEqual(self.client.post('/api/start',json=body).status_code,422)
        self.assertEqual(self.client.post('/api/advance',json={'steps':100000}).status_code,422)


if __name__ == '__main__': unittest.main()
