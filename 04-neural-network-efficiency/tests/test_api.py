import unittest
from fastapi.testclient import TestClient
from app import app

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.client=TestClient(app)

    def test_index(self):
        r=self.client.get('/')
        self.assertEqual(r.status_code,200)
        self.assertIn('Neural Network Efficiency Lab',r.text)

    def test_real_results(self):
        r=self.client.get('/api/overview')
        self.assertEqual(r.status_code,200)
        data=r.json()['results']
        self.assertEqual(len(data['models']),3)
        self.assertEqual(data['split']['test'],10000)
        self.assertLess(data['models'][0]['macs']['total'],75000)
        self.assertGreater(data['models'][0]['test_accuracy'],0.85)

    def test_architecture(self):
        r=self.client.get('/api/architecture?c1=3&c2=6&kernel=3')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['macs']['total'],55860)
        self.assertIsNone(r.json()['accuracy'])
        self.assertTrue(r.json()['budget_met'])
        self.assertEqual(self.client.get('/api/architecture?c1=100&c2=6&kernel=3').status_code,400)

    def test_sample_and_pixels_prediction(self):
        s=self.client.get('/api/examples').json()['samples'][0]
        r=self.client.post('/api/predict',json={'model_id':'micro','sample_id':s['id']})
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['probabilities']),10)
        r=self.client.post('/api/predict',json={'model_id':'compact','pixels':[[0]*28 for _ in range(28)]})
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['features']),8)

    def test_bad_prediction_inputs(self):
        examples=[{'model_id':'made-up','pixels':[[0]*28]*28},
                  {'model_id':'micro','sample_id':'../../x'},
                  {'model_id':'micro','pixels':[[0]*28]*27},
                  {'model_id':'micro','pixels':[[500]*28]*28}]
        for p in examples:
            with self.subTest(payload=p):
                self.assertEqual(self.client.post('/api/predict',json=p).status_code,400)

if __name__=='__main__':unittest.main()
