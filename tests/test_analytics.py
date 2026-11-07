#!/usr/bin/env python3
"""
ForensiTap-ESP32: Forensic Collector & Analytics Unit Tests
Stage 14 Implementation

Tests telemetry ingestion, device aggregation, statistical calculation,
and cryptographic evidence verification on simulated session logs.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laptop.analytics.traffic_analysis import ForensicTrafficAnalyzer, compute_sha256, build_canonical, GENESIS_PREV_HASH

class TestTrafficAnalytics(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forensitap_test_session_")

        # Create mock session files
        self.meta_path = os.path.join(self.test_dir, "session_meta.json")
        self.telemetry_path = os.path.join(self.test_dir, "telemetry.jsonl")
        self.devices_path = os.path.join(self.test_dir, "devices.jsonl")
        self.evidence_path = os.path.join(self.test_dir, "evidence_chain.jsonl")

        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": "test_session_001",
                "start_iso": "2026-11-07T22:00:00",
                "duration_sec": 30.0
            }, f)

        # Write mock telemetry
        with open(self.telemetry_path, "w", encoding="utf-8") as f:
            for fps in [80.0, 100.0, 120.0, 90.0, 110.0]:
                record = {
                    "timestamp": 1700000000.0,
                    "stats": {
                        "current_frame_rate": fps,
                        "total_observed_frames": 5000,
                        "management_frame_count": 1000,
                        "data_frame_count": 4000,
                        "dropped_frames_count": 0
                    },
                    "features": {
                        "frame_rate": fps,
                        "byte_rate": fps * 200.0,
                        "management_frame_ratio": 0.20,
                        "traffic_burst_score": 1.5
                    }
                }
                f.write(json.dumps(record) + "\n")

        # Write mock devices
        with open(self.devices_path, "w", encoding="utf-8") as f:
            dev_snap = {
                "devices": [
                    {"mac": "64:FB:92:C0:14:80", "is_ap": True, "packets": 3000, "rssi": -55},
                    {"mac": "04:C8:07:2A:30:14", "is_ap": False, "packets": 1500, "rssi": -65},
                    {"mac": "80:9D:65:47:9B:52", "is_ap": False, "packets": 500, "rssi": -78}
                ]
            }
            f.write(json.dumps(dev_snap) + "\n")

        # Write mock evidence chain
        g_canon = build_canonical(0, 100, "SYSTEM_BOOT", "INFO", "Genesis", GENESIS_PREV_HASH)
        g_hash = compute_sha256(g_canon)

        b1_canon = build_canonical(1, 1500, "NEW_DEVICE", "INFO", "Device 1", g_hash)
        b1_hash = compute_sha256(b1_canon)

        with open(self.evidence_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"index": 0, "timestamp_ms": 100, "event_type": "SYSTEM_BOOT", "severity": "INFO", "description": "Genesis", "prev_hash": GENESIS_PREV_HASH, "block_hash": g_hash}) + "\n")
            f.write(json.dumps({"index": 1, "timestamp_ms": 1500, "event_type": "NEW_DEVICE", "severity": "INFO", "description": "Device 1", "prev_hash": g_hash, "block_hash": b1_hash}) + "\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_analyzer_load(self):
        analyzer = ForensicTrafficAnalyzer(self.test_dir)
        self.assertTrue(analyzer.load_data())
        self.assertEqual(len(analyzer.telemetry_records), 5)
        self.assertEqual(len(analyzer.device_snapshots), 1)
        self.assertEqual(len(analyzer.evidence_blocks), 2)

    def test_throughput_metrics(self):
        analyzer = ForensicTrafficAnalyzer(self.test_dir)
        analyzer.load_data()
        metrics = analyzer.analyze_throughput()
        self.assertEqual(metrics["samples"], 5)
        self.assertEqual(metrics["fps_min"], 80.0)
        self.assertEqual(metrics["fps_max"], 120.0)
        self.assertEqual(metrics["fps_mean"], 100.0)
        self.assertEqual(metrics["total_observed_frames"], 5000)
        self.assertEqual(metrics["dropped_frames"], 0)

    def test_device_analysis(self):
        analyzer = ForensicTrafficAnalyzer(self.test_dir)
        analyzer.load_data()
        devs = analyzer.analyze_devices()
        self.assertEqual(devs["unique_devices"], 3)
        self.assertEqual(devs["ap_count"], 1)
        self.assertEqual(devs["sta_count"], 2)
        self.assertEqual(devs["top_devices"][0]["mac"], "64:FB:92:C0:14:80")
        self.assertEqual(devs["top_devices"][0]["packets"], 3000)

    def test_evidence_chain_audit(self):
        analyzer = ForensicTrafficAnalyzer(self.test_dir)
        analyzer.load_data()
        audit = analyzer.audit_evidence_chain()
        self.assertTrue(audit["is_valid"])
        self.assertEqual(audit["count"], 2)

    def test_tamper_detection(self):
        # Tamper block 1 in evidence_chain.jsonl
        analyzer = ForensicTrafficAnalyzer(self.test_dir)
        analyzer.load_data()
        analyzer.evidence_blocks[1]["description"] = "TAMPERED PAYLOAD"
        audit = analyzer.audit_evidence_chain()
        self.assertFalse(audit["is_valid"])
        self.assertEqual(audit["status"], "TAMPERED")
        self.assertEqual(audit["failed_index"], 1)

if __name__ == '__main__':
    unittest.main()
