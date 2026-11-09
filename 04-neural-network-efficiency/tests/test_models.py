import unittest
import torch
from neural_lab.models import Architecture, PRESETS, DigitCNN, mac_breakdown, param_count, preprocess
from neural_lab.inference import ModelRegistry

class ModelTests(unittest.TestCase):
    def test_forward_and_feature_shapes(self):
        for c in PRESETS:
            with self.subTest(c=c.id):
                model=DigitCNN(c)
                y,features=model(torch.zeros(2,1,28,28),return_features=True)
                self.assertEqual(tuple(y.shape),(2,10))
                self.assertEqual(tuple(features[0].shape),(2,c.c1,28,28))
                self.assertEqual(tuple(features[1].shape),(2,c.c2,14,14))

    def test_budget_and_operation_count(self):
        self.assertEqual(mac_breakdown(PRESETS[0])['total'],55860)
        self.assertEqual(mac_breakdown(PRESETS[1])['total'],290080)
        self.assertEqual(mac_breakdown(PRESETS[2])['total'],1031744)
        self.assertLess(mac_breakdown(PRESETS[0])['total'],75000)
        self.assertEqual(param_count(PRESETS[0]),3148)

    def test_invalid_architecture(self):
        for c in [Architecture('bad','Bad',1,6,3),Architecture('bad','Bad',6,8,7),Architecture('bad','Bad',66,8,3)]:
            with self.assertRaises(ValueError): DigitCNN(c)

    def test_preprocessing_validation(self):
        with self.assertRaises(ValueError): preprocess([[0]*28]*27)
        with self.assertRaises(ValueError): preprocess([[256]*28]*28)
        with self.assertRaises(ValueError): preprocess([[float('nan')]*28]*28)
        self.assertEqual(tuple(preprocess([[0]*28]*28).shape),(1,1,28,28))

    def test_saved_models_predict(self):
        from pathlib import Path
        reg=ModelRegistry(Path(__file__).resolve().parents[1]/'checkpoints')
        for cfg in PRESETS:
            with self.subTest(model=cfg.id):
                result=reg.predict(cfg.id,[[0]*28 for _ in range(28)])
                self.assertEqual(len(result['probabilities']),10)
                self.assertAlmostEqual(sum(result['probabilities']),1,places=5)
                self.assertEqual(len(result['features']), min(4,cfg.c1) + min(4,cfg.c2))
                self.assertGreaterEqual(result['digit'],0)
                self.assertLessEqual(result['digit'],9)

if __name__=='__main__':unittest.main()
