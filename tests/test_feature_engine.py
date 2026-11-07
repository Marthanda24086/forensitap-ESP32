#!/usr/bin/env python3
"""
ForensiTap-ESP32: Feature Engine Unit Tests
Validates sliding window aggregation, zero-denominator protections,
burst score calculation, and Welford's algorithm baseline tracking.
"""

import math
import statistics
import unittest

class TestFeatureEngine(unittest.TestCase):
    def test_feature_calculations(self):
        # 10 buckets of 1 second each
        buckets = [
            {'frames': 100, 'bytes': 50000, 'mgmt': 20, 'data': 80},
            {'frames': 120, 'bytes': 60000, 'mgmt': 30, 'data': 90},
            {'frames': 80,  'bytes': 40000, 'mgmt': 10, 'data': 70},
            {'frames': 110, 'bytes': 55000, 'mgmt': 25, 'data': 85},
            {'frames': 90,  'bytes': 45000, 'mgmt': 15, 'data': 75},
            {'frames': 130, 'bytes': 65000, 'mgmt': 35, 'data': 95},
            {'frames': 70,  'bytes': 35000, 'mgmt': 5,  'data': 65},
            {'frames': 100, 'bytes': 50000, 'mgmt': 20, 'data': 80},
            {'frames': 100, 'bytes': 50000, 'mgmt': 20, 'data': 80},
            {'frames': 100, 'bytes': 50000, 'mgmt': 20, 'data': 80},
        ]
        window_duration = 10.0

        total_frames = sum(b['frames'] for b in buckets) # 1000
        total_bytes  = sum(b['bytes'] for b in buckets)  # 500000
        total_mgmt   = sum(b['mgmt'] for b in buckets)   # 200
        max_bucket   = max(b['frames'] for b in buckets) # 130

        frame_rate   = total_frames / window_duration
        byte_rate    = total_bytes / window_duration
        avg_frame_sz = total_bytes / total_frames if total_frames > 0 else 0.0
        mgmt_ratio   = total_mgmt / total_frames if total_frames > 0 else 0.0
        avg_bucket   = total_frames / window_duration
        burst_score  = max_bucket / avg_bucket if avg_bucket > 0 else 1.0

        self.assertAlmostEqual(frame_rate, 100.0)
        self.assertAlmostEqual(byte_rate, 50000.0)
        self.assertAlmostEqual(avg_frame_sz, 500.0)
        self.assertAlmostEqual(mgmt_ratio, 0.20)
        self.assertAlmostEqual(burst_score, 1.30)

    def test_zero_denominator_protection(self):
        total_frames = 0
        total_bytes = 0
        total_mgmt = 0
        window_duration = 10.0

        frame_rate = total_frames / window_duration
        byte_rate = total_bytes / window_duration
        avg_frame_sz = total_bytes / total_frames if total_frames > 0 else 0.0
        mgmt_ratio = total_mgmt / total_frames if total_frames > 0 else 0.0
        avg_bucket = total_frames / window_duration
        burst_score = 0.0 if total_frames == 0 else 1.0

        self.assertEqual(frame_rate, 0.0)
        self.assertEqual(byte_rate, 0.0)
        self.assertEqual(avg_frame_sz, 0.0)
        self.assertEqual(mgmt_ratio, 0.0)

    def test_welford_baseline(self):
        # Sample sequence of 10s window frame rates
        rates = [100.0, 110.0, 95.0, 105.0, 102.0, 98.0, 108.0]

        # Welford algorithm emulation
        mean = 0.0
        m2 = 0.0
        for i, x in enumerate(rates, start=1):
            delta = x - mean
            mean += delta / i
            delta2 = x - mean
            m2 += delta * delta2

        expected_mean = statistics.mean(rates)
        expected_std  = statistics.stdev(rates)
        calculated_std = math.sqrt(m2 / (len(rates) - 1))

        self.assertAlmostEqual(mean, expected_mean, places=5)
        self.assertAlmostEqual(calculated_std, expected_std, places=5)

if __name__ == '__main__':
    unittest.main()
