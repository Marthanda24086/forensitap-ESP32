#!/usr/bin/env python3
"""
ForensiTap-ESP32: Rule-Based Anomaly Detector Unit Tests
Validates the five deterministic detection rules, threshold evaluation,
alert deduplication with cooldowns, and FIFO circular ring buffer behavior.
"""

import unittest
from typing import List, Dict, Optional

class SecurityAlert:
    def __init__(self, event_id: int, timestamp_ms: int, event_type: str, severity: str, description: str):
        self.event_id = event_id
        self.timestamp_ms = timestamp_ms
        self.event_type = event_type
        self.severity = severity
        self.description = description

class DetectorSimulator:
    MAX_ALERTS = 16

    def __init__(self, spike_z: float = 3.0, mgmt_ratio: float = 0.60, burst_score: float = 5.0, cooldown_ms: int = 30000):
        self.spike_z = spike_z
        self.mgmt_ratio_threshold = mgmt_ratio
        self.burst_score_threshold = burst_score
        self.cooldown_ms = cooldown_ms

        self.alerts: List[SecurityAlert] = []
        self.total_alerts = 0
        self.last_traffic_spike_ms = 0
        self.last_mgmt_anomaly_ms = 0
        self.last_burst_alert_ms = 0
        self.last_health_alert_ms = 0
        self.last_observed_dropped = 0

    def raise_alert(self, current_ms: int, event_type: str, severity: str, desc: str):
        self.total_alerts += 1
        alert = SecurityAlert(self.total_alerts, current_ms, event_type, severity, desc)
        if len(self.alerts) < self.MAX_ALERTS:
            self.alerts.append(alert)
        else:
            # Shift left (FIFO ring buffer)
            self.alerts.pop(0)
            self.alerts.append(alert)

    def evaluate_features(self, feat: Dict, current_ms: int, dropped_frames: int):
        # Rule 1: Traffic Spike
        z_score = feat.get('rate_deviation_z_score', 0.0)
        fps = feat.get('frame_rate_fps', 0.0)
        mean_fps = feat.get('baseline_mean_fps', 0.0)
        if z_score >= self.spike_z and fps > 20.0 and mean_fps > 5.0:
            if current_ms - self.last_traffic_spike_ms >= self.cooldown_ms or self.last_traffic_spike_ms == 0:
                self.raise_alert(current_ms, "TRAFFIC_SPIKE_DETECTED", "WARNING", f"Traffic spike: {fps:.1f} fps (Z={z_score:.2f})")
                self.last_traffic_spike_ms = current_ms

        # Rule 2: Management Anomaly
        mgmt_ratio = feat.get('mgmt_frame_ratio', 0.0)
        total_frames = feat.get('window_frame_count', 0)
        if mgmt_ratio >= self.mgmt_ratio_threshold and total_frames >= 20:
            if current_ms - self.last_mgmt_anomaly_ms >= self.cooldown_ms or self.last_mgmt_anomaly_ms == 0:
                self.raise_alert(current_ms, "MGMT_FRAME_FLOOD", "WARNING", f"Excessive mgmt frames: {mgmt_ratio*100:.1f}%")
                self.last_mgmt_anomaly_ms = current_ms

        # Rule 4: Activity Burst
        burst = feat.get('burstiness_score', 1.0)
        if burst >= self.burst_score_threshold and total_frames >= 10:
            if current_ms - self.last_burst_alert_ms >= self.cooldown_ms or self.last_burst_alert_ms == 0:
                self.raise_alert(current_ms, "ACTIVITY_BURST", "WARNING", f"Traffic burst score: {burst:.2f}")
                self.last_burst_alert_ms = current_ms

        # Rule 5: Monitoring Health
        if dropped_frames > self.last_observed_dropped:
            delta = dropped_frames - self.last_observed_dropped
            if current_ms - self.last_health_alert_ms >= self.cooldown_ms or self.last_health_alert_ms == 0:
                self.raise_alert(current_ms, "BUFFER_OVERFLOW_RISK", "ERROR", f"Buffer overflow: {delta} frames dropped")
                self.last_health_alert_ms = current_ms
            self.last_observed_dropped = dropped_frames

    def notify_new_device(self, current_ms: int, mac: str, is_ap: bool, rssi: int):
        dev_type = "AP" if is_ap else "Station"
        self.raise_alert(current_ms, "NEW_DEVICE_OBSERVED", "INFO", f"New {dev_type} discovered: {mac} (RSSI: {rssi} dBm)")


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = DetectorSimulator()

    def test_rule1_traffic_spike(self):
        # Baseline mean 100 fps, current 450 fps -> Z = 3.5 (> 3.0)
        feat = {
            'rate_deviation_z_score': 3.5,
            'frame_rate_fps': 450.0,
            'baseline_mean_fps': 100.0,
            'mgmt_frame_ratio': 0.1,
            'window_frame_count': 4500,
            'burstiness_score': 1.2
        }
        self.detector.evaluate_features(feat, current_ms=10000, dropped_frames=0)
        self.assertEqual(len(self.detector.alerts), 1)
        self.assertEqual(self.detector.alerts[0].event_type, "TRAFFIC_SPIKE_DETECTED")
        self.assertEqual(self.detector.alerts[0].severity, "WARNING")

        # Second evaluation within 30s cooldown should NOT trigger duplicate alert
        self.detector.evaluate_features(feat, current_ms=20000, dropped_frames=0)
        self.assertEqual(len(self.detector.alerts), 1)

        # After cooldown expired (30s+), new spike should trigger
        self.detector.evaluate_features(feat, current_ms=45000, dropped_frames=0)
        self.assertEqual(len(self.detector.alerts), 2)

    def test_rule2_management_anomaly(self):
        # Management ratio 0.75 (> 0.60 threshold)
        feat = {
            'rate_deviation_z_score': 0.5,
            'frame_rate_fps': 50.0,
            'baseline_mean_fps': 50.0,
            'mgmt_frame_ratio': 0.75,
            'window_frame_count': 500,
            'burstiness_score': 1.1
        }
        self.detector.evaluate_features(feat, current_ms=10000, dropped_frames=0)
        self.assertEqual(len(self.detector.alerts), 1)
        self.assertEqual(self.detector.alerts[0].event_type, "MGMT_FRAME_FLOOD")

    def test_rule3_new_device(self):
        self.detector.notify_new_device(5000, "AA:BB:CC:DD:EE:FF", False, -65)
        self.assertEqual(len(self.detector.alerts), 1)
        self.assertEqual(self.detector.alerts[0].event_type, "NEW_DEVICE_OBSERVED")
        self.assertEqual(self.detector.alerts[0].severity, "INFO")
        self.assertIn("AA:BB:CC:DD:EE:FF", self.detector.alerts[0].description)

    def test_rule4_activity_burst(self):
        feat = {
            'rate_deviation_z_score': 1.0,
            'frame_rate_fps': 20.0,
            'baseline_mean_fps': 20.0,
            'mgmt_frame_ratio': 0.1,
            'window_frame_count': 200,
            'burstiness_score': 6.2  # > 5.0 threshold
        }
        self.detector.evaluate_features(feat, current_ms=10000, dropped_frames=0)
        self.assertEqual(len(self.detector.alerts), 1)
        self.assertEqual(self.detector.alerts[0].event_type, "ACTIVITY_BURST")

    def test_rule5_monitoring_health(self):
        feat = {'rate_deviation_z_score': 0.0, 'frame_rate_fps': 10.0, 'baseline_mean_fps': 10.0, 'mgmt_frame_ratio': 0.1, 'window_frame_count': 10, 'burstiness_score': 1.0}
        self.detector.evaluate_features(feat, current_ms=1000, dropped_frames=5)
        self.assertEqual(len(self.detector.alerts), 1)
        self.assertEqual(self.detector.alerts[0].event_type, "BUFFER_OVERFLOW_RISK")
        self.assertEqual(self.detector.alerts[0].severity, "ERROR")

    def test_ring_buffer_fifo_eviction(self):
        # Produce 20 alerts into a 16-slot buffer
        for i in range(1, 21):
            self.detector.notify_new_device(i * 1000, f"00:11:22:33:44:{i:02X}", False, -70)

        self.assertEqual(len(self.detector.alerts), 16)
        self.assertEqual(self.detector.total_alerts, 20)
        # Oldest alerts (1..4) should have been evicted; first element should now be alert 5
        self.assertEqual(self.detector.alerts[0].event_id, 5)
        self.assertEqual(self.detector.alerts[-1].event_id, 20)

if __name__ == '__main__':
    unittest.main()
