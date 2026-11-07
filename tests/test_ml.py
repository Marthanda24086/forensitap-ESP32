#!/usr/bin/env python3
"""
ForensiTap-ESP32: Machine Learning Anomaly Detection Unit Tests
Stage 17 Implementation

Tests robust model fitting, JSON persistence, threshold calibration,
and classification discrimination between benign samples and wireless attacks.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laptop.ml.train import RobustAnomalyDetector, FEATURE_NAMES, generate_synthetic_baseline

class TestMLAnomalyDetector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forensitap_ml_test_")
        self.model_path = os.path.join(self.test_dir, "test_model.json")
        self.training_data = generate_synthetic_baseline()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_training_and_threshold(self):
        detector = RobustAnomalyDetector(contamination=0.03)
        detector.fit(self.training_data)

        self.assertTrue(detector.is_trained)
        self.assertGreater(detector.threshold, 2.0)
        self.assertEqual(len(detector.medians), len(FEATURE_NAMES))
        self.assertEqual(len(detector.mads), len(FEATURE_NAMES))

        for name in FEATURE_NAMES:
            self.assertIn(name, detector.medians)
            self.assertGreater(detector.mads[name], 0.0)

    def test_model_persistence(self):
        detector = RobustAnomalyDetector(contamination=0.03)
        detector.fit(self.training_data)
        detector.save(self.model_path)

        self.assertTrue(os.path.exists(self.model_path))

        loaded = RobustAnomalyDetector.load(self.model_path)
        self.assertTrue(loaded.is_trained)
        self.assertEqual(loaded.threshold, detector.threshold)
        self.assertEqual(loaded.medians, detector.medians)

    def test_benign_vs_anomaly_discrimination(self):
        detector = RobustAnomalyDetector(contamination=0.03)
        detector.fit(self.training_data)

        # 1. Benign sample
        benign = {
            "frame_rate": 102.0, "byte_rate": 20400.0, "average_frame_size": 200.0,
            "unique_peers": 16, "management_frame_ratio": 0.18,
            "traffic_burst_score": 1.7, "frame_rate_zscore": 0.1
        }
        res_benign = detector.score_sample(benign)
        self.assertFalse(res_benign["is_anomaly"])
        self.assertLess(res_benign["anomaly_probability"], 0.20)

        # 2. Deauthentication Flood Attack
        deauth_flood = {
            "frame_rate": 400.0, "byte_rate": 20000.0, "average_frame_size": 50.0,
            "unique_peers": 3, "management_frame_ratio": 0.92,
            "traffic_burst_score": 5.0, "frame_rate_zscore": 5.0
        }
        res_attack = detector.score_sample(deauth_flood)
        self.assertTrue(res_attack["is_anomaly"])
        self.assertGreater(res_attack["anomaly_probability"], 0.95)
        self.assertGreater(res_attack["distance"], detector.threshold)

        # Confirm attribution spotlights management frame ratio
        self.assertGreater(res_attack["attributions"]["management_frame_ratio"], 10.0)

if __name__ == '__main__':
    unittest.main()
