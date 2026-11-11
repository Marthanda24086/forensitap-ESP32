#!/usr/bin/env python3
"""
Unit tests for ForensiTap ESP32 Dashboard Communication Parser (USB Serial & Wi-Fi Telemetry)
Validates:
- Type A: Structured @FEATURES JSON parsing
- Type B: Standard JSON payload parsing
- Type C: Diagnostic log extraction (Heartbeat, 10s Window Rates, Baseline, Peers)
- Wi-Fi IP auto-detection & IPv4 validation
- Chunk buffering & split line handling
- Resilience against noise, corrupt packets, and malformed strings
"""

import json
import re
import unittest

def is_valid_ipv4(ip: str) -> bool:
    if not ip or not isinstance(ip, str):
        return False
    parts = ip.strip().split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False
    if ip == '0.0.0.0' or ip == '255.255.255.255':
        return False
    return True

def extract_ip_from_line(line: str):
    pattern = r'(?:(?:\[NET\]\s*)?IPv4 Address\s*:\s*|DHCP Lease Granted!\s*IPv4:\s*|Local IP\s*:\s*)([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})'
    match = re.search(pattern, line, re.IGNORECASE)
    if match and is_valid_ipv4(match.group(1)):
        return match.group(1)
    return None

def to_valid_number(val):
    if val is None or val == '':
        return None
    try:
        f = float(val)
        return f
    except (ValueError, TypeError):
        return None

class ForensiTapSerialParserSimulator:
    """
    Python reference implementation of the dashboard's handleSerialLine() and buffer.
    Ensures identical logic and behavior as app.js.
    """
    def __init__(self):
        self.buffer = ""
        self.detected_ip = None
        self.latest_features = {}
        self.activity_count = 0

    def feed_chunk(self, chunk: str):
        self.buffer += chunk
        lines = re.split(r'\r?\n', self.buffer)
        self.buffer = lines.pop() # Retain incomplete line
        for line in lines:
            self.handle_line(line)

    def handle_line(self, line: str):
        if not line:
            return
        trimmed = line.strip()
        if not trimmed:
            return

        # Type A: Structured Telemetry Message (@FEATURES {...})
        if trimmed.startswith('@FEATURES '):
            payload_str = trimmed[10:].strip()
            try:
                data = json.loads(payload_str)
                # Validate numeric payload
                valid_num = False
                for k in ("frame_rate", "throughput_kbps", "byte_rate", "unique_peers"):
                    if to_valid_number(data.get(k)) is not None:
                        valid_num = True
                        break
                if not valid_num:
                    return

                ip = data.get("ip_address")
                if ip and is_valid_ipv4(ip):
                    self.detected_ip = ip
                self.normalize_and_update(data)
                self.activity_count += 1
                return
            except Exception:
                return

        # Type B: Standard JSON Payload ({...})
        if trimmed.startswith('{') and trimmed.endswith('}'):
            try:
                data = json.loads(trimmed)
                valid_num = False
                for k in ("frame_rate", "throughput_kbps", "byte_rate", "unique_peers"):
                    if to_valid_number(data.get(k)) is not None:
                        valid_num = True
                        break
                if not valid_num:
                    return

                ip = data.get("ip_address")
                if ip and is_valid_ipv4(ip):
                    self.detected_ip = ip
                self.normalize_and_update(data)
                self.activity_count += 1
                return
            except Exception:
                pass

        # Type C: Human-Readable Diagnostic Logs
        # 1. IP extraction
        ip = extract_ip_from_line(trimmed)
        if ip:
            self.detected_ip = ip

        # 2. Heartbeat extraction
        if '[HEARTBEAT]' in trimmed:
            hb_fps = re.search(r'([0-9.]+)\s*fps', trimmed, re.I)
            hb_peers = re.search(r'(\d+)\s*peers', trimmed, re.I)
            hb_alerts = re.search(r'Alerts:\s*(\d+)', trimmed, re.I)
            hb_uptime = re.search(r'Uptime:\s*(\d+)\s*s', trimmed, re.I)

            if hb_fps or hb_peers or hb_alerts:
                data = {}
                if hb_fps:
                    data["frame_rate"] = float(hb_fps.group(1))
                if hb_peers:
                    data["unique_peers"] = int(hb_peers.group(1))
                if hb_alerts:
                    data["alerts_total"] = int(hb_alerts.group(1))
                if hb_uptime:
                    data["uptime_sec"] = int(hb_uptime.group(1))

                self.normalize_and_update(data)
                self.activity_count += 1
                return

        # 3. 10s Window Rates extraction
        rates_pattern = r'10s Window Rates:\s*([0-9.]+)\s*fps\s*\|\s*([0-9.]+)\s*KB\/s\s*\|\s*Deauth:\s*([0-9.]+)\s*fps'
        rates_match = re.search(rates_pattern, trimmed, re.IGNORECASE)
        if rates_match:
            kb_per_sec = float(rates_match.group(2))
            data = {
                "frame_rate": float(rates_match.group(1)),
                "byte_rate": kb_per_sec * 1024.0,
                "throughput_kbps": kb_per_sec * 8.0,
                "deauth_rate": float(rates_match.group(3))
            }
            self.normalize_and_update(data)
            self.activity_count += 1
            return

        # 4. Unique peers and burst score
        pb_pattern = r'Unique Peers\s*:\s*(\d+)\s*devices\s*\|\s*Burst Score:\s*([0-9.]+)'
        pb_match = re.search(pb_pattern, trimmed, re.IGNORECASE)
        if pb_match:
            self.normalize_and_update({
                "unique_peers": int(pb_match.group(1)),
                "traffic_burst_score": float(pb_match.group(2))
            })
            self.activity_count += 1
            return

        # 5. Baseline profile
        base_pattern = r'Baseline Profile:\s*Welford:\s*([0-9.]+)\s*fps\s*\|\s*EWMA:\s*([0-9.]+)\s*fps\s*\|\s*Z-Score:\s*([+-]?[0-9.]+)'
        base_match = re.search(base_pattern, trimmed, re.IGNORECASE)
        if base_match:
            self.normalize_and_update({
                "baseline": {
                    "warmup_ready": True,
                    "mean_frame_rate": float(base_match.group(1)),
                    "ewma_mean_frame_rate": float(base_match.group(2)),
                    "frame_rate_zscore": float(base_match.group(3))
                }
            })
            self.activity_count += 1
            return

        # 3. 10s Window Rates extraction
        rates_pattern = r'10s Window Rates:\s*([0-9.]+)\s*fps\s*\|\s*([0-9.]+)\s*KB\/s\s*\|\s*Deauth:\s*([0-9.]+)\s*fps'
        rates_match = re.search(rates_pattern, trimmed, re.IGNORECASE)
        if rates_match:
            kb_per_sec = float(rates_match.group(2))
            data = {
                "frame_rate": float(rates_match.group(1)),
                "byte_rate": kb_per_sec * 1024.0,
                "throughput_kbps": kb_per_sec * 8.0,
                "deauth_rate": float(rates_match.group(3))
            }
            self.normalize_and_update(data)
            self.activity_count += 1
            return

        # 4. Unique peers and burst score
        pb_pattern = r'Unique Peers\s*:\s*(\d+)\s*devices\s*\|\s*Burst Score:\s*([0-9.]+)'
        pb_match = re.search(pb_pattern, trimmed, re.IGNORECASE)
        if pb_match:
            self.normalize_and_update({
                "unique_peers": int(pb_match.group(1)),
                "traffic_burst_score": float(pb_match.group(2))
            })
            self.activity_count += 1
            return

        # 5. Baseline profile
        base_pattern = r'Baseline Profile:\s*Welford:\s*([0-9.]+)\s*fps\s*\|\s*EWMA:\s*([0-9.]+)\s*fps\s*\|\s*Z-Score:\s*([+-]?[0-9.]+)'
        base_match = re.search(base_pattern, trimmed, re.IGNORECASE)
        if base_match:
            self.normalize_and_update({
                "baseline": {
                    "warmup_ready": True,
                    "mean_frame_rate": float(base_match.group(1)),
                    "ewma_mean_frame_rate": float(base_match.group(2)),
                    "frame_rate_zscore": float(base_match.group(3))
                }
            })
            self.activity_count += 1
            return

    def normalize_and_update(self, data: dict):
        for k, v in data.items():
            if v is not None:
                self.latest_features[k] = v


class TestSerialParser(unittest.TestCase):
    def setUp(self):
        self.parser = ForensiTapSerialParserSimulator()

    def test_type_a_structured_telemetry(self):
        """Test Type A @FEATURES JSON line parsing"""
        line = '@FEATURES {"frame_rate":94.5,"throughput_kbps":32.1,"byte_rate":4012.8,"deauth_rate":0.0,"disassoc_rate":0.0,"deauth_ratio":0.000,"burst_score":1.20,"mgmt_ratio":0.120,"unique_peers":6,"uptime_sec":15,"alerts_total":0,"wifi_connected":true,"ip_address":"192.168.1.45"}'
        self.parser.handle_line(line)

        self.assertEqual(self.parser.detected_ip, "192.168.1.45")
        self.assertAlmostEqual(self.parser.latest_features["frame_rate"], 94.5)
        self.assertAlmostEqual(self.parser.latest_features["throughput_kbps"], 32.1)
        self.assertEqual(self.parser.latest_features["unique_peers"], 6)
        self.assertEqual(self.parser.latest_features["uptime_sec"], 15)
        self.assertEqual(self.parser.latest_features["alerts_total"], 0)
        self.assertTrue(self.parser.latest_features["wifi_connected"])
        self.assertEqual(self.parser.activity_count, 1)

    def test_type_b_regular_json(self):
        """Test Type B legacy JSON message parsing"""
        line = '{"frame_rate":88.2,"deauth_rate":1.5,"unique_peers":4,"uptime_sec":42}'
        self.parser.handle_line(line)

        self.assertAlmostEqual(self.parser.latest_features["frame_rate"], 88.2)
        self.assertAlmostEqual(self.parser.latest_features["deauth_rate"], 1.5)
        self.assertEqual(self.parser.latest_features["unique_peers"], 4)
        self.assertEqual(self.parser.latest_features["uptime_sec"], 42)
        self.assertEqual(self.parser.activity_count, 1)

    def test_type_c_heartbeat_diagnostics(self):
        """Test Type C Heartbeat log line parsing"""
        line = '[15000] [INFO] [LIV ] [HEARTBEAT] ForensiTap | WIFI_CONNECTED | MON_ACTIVE | API_ACTIVE | 94 fps | 6 peers | Alerts: 0 | Blocks: 1 | Uptime: 15 s | Heap: 215432 B'
        self.parser.handle_line(line)

        self.assertAlmostEqual(self.parser.latest_features["frame_rate"], 94.0)
        self.assertEqual(self.parser.latest_features["unique_peers"], 6)
        self.assertEqual(self.parser.latest_features["alerts_total"], 0)
        self.assertEqual(self.parser.latest_features["uptime_sec"], 15)
        self.assertEqual(self.parser.activity_count, 1)

    def test_type_c_window_rates_diagnostics(self):
        """Test Type C 10s Window Rates log line parsing"""
        line = '  |   10s Window Rates: 94.5 fps | 32.1 KB/s | Deauth: 0.0 fps'
        self.parser.handle_line(line)

        self.assertAlmostEqual(self.parser.latest_features["frame_rate"], 94.5)
        self.assertAlmostEqual(self.parser.latest_features["throughput_kbps"], 32.1 * 8.0)
        self.assertAlmostEqual(self.parser.latest_features["deauth_rate"], 0.0)
        self.assertEqual(self.parser.activity_count, 1)

    def test_type_c_peers_and_baseline_diagnostics(self):
        """Test Type C subsystem diagnostic lines"""
        line1 = '  |   Unique Peers    : 8 devices | Burst Score: 1.45'
        line2 = '  |   Baseline Profile: Welford: 92.4 fps | EWMA: 93.1 fps | Z-Score: +0.22'
        self.parser.handle_line(line1)
        self.parser.handle_line(line2)

        self.assertEqual(self.parser.latest_features["unique_peers"], 8)
        self.assertAlmostEqual(self.parser.latest_features["traffic_burst_score"], 1.45)
        self.assertAlmostEqual(self.parser.latest_features["baseline"]["mean_frame_rate"], 92.4)
        self.assertAlmostEqual(self.parser.latest_features["baseline"]["ewma_mean_frame_rate"], 93.1)
        self.assertAlmostEqual(self.parser.latest_features["baseline"]["frame_rate_zscore"], 0.22)
        self.assertEqual(self.parser.activity_count, 2)

    def test_ip_address_detection_and_validation(self):
        """Test IP extraction from log lines and IP validation"""
        lines = [
            "[2100] [INFO] [NET ] DHCP Lease Granted! IPv4: 192.168.1.105 | Channel: 11 | RSSI: -52 dBm",
            "[2101] [INFO] [NET ] [NET] IPv4 Address : 192.168.1.105",
            "  |   IPv4 Address    : 192.168.1.105"
        ]
        for l in lines:
            self.parser.handle_line(l)
            self.assertEqual(self.parser.detected_ip, "192.168.1.105")

        # Invalid IPs should be rejected
        self.assertFalse(is_valid_ipv4("0.0.0.0"))
        self.assertFalse(is_valid_ipv4("255.255.255.255"))
        self.assertFalse(is_valid_ipv4("999.168.1.1"))
        self.assertFalse(is_valid_ipv4("192.168.1"))
        self.assertFalse(is_valid_ipv4("not_an_ip"))
        self.assertTrue(is_valid_ipv4("192.168.1.45"))
        self.assertTrue(is_valid_ipv4("10.0.0.1"))

    def test_chunked_streaming_and_split_packets(self):
        """Test partial chunk buffering when serial packets arrive split across reads"""
        chunk1 = "@FEATURES {\"frame_rate\":92.0"
        chunk2 = ",\"throughput_kbps\":28.4,\"byte_rate\":3550.0,\"deauth_rate\":0.0,"
        chunk3 = "\"disassoc_rate\":0.0,\"deauth_ratio\":0.0,\"burst_score\":1.1,"
        chunk4 = "\"mgmt_ratio\":0.1,\"unique_peers\":5,\"uptime_sec\":100,\"alerts_total\":1,\"wifi_connected\":true,\"ip_address\":\"192.168.1.77\"}\n"

        self.parser.feed_chunk(chunk1)
        self.assertEqual(self.parser.activity_count, 0) # incomplete

        self.parser.feed_chunk(chunk2)
        self.assertEqual(self.parser.activity_count, 0) # incomplete

        self.parser.feed_chunk(chunk3)
        self.assertEqual(self.parser.activity_count, 0) # incomplete

        self.parser.feed_chunk(chunk4)
        self.assertEqual(self.parser.activity_count, 1) # completed!
        self.assertAlmostEqual(self.parser.latest_features["frame_rate"], 92.0)
        self.assertEqual(self.parser.detected_ip, "192.168.1.77")

    def test_noise_and_malformed_lines_resilience(self):
        """Test resilience against garbled serial noise, invalid JSON, and partial corrupt data"""
        noise_lines = [
            "",
            "   ",
            "~~~????@@@",
            "@FEATURES {invalid json here",
            "{'single_quotes': 'not_valid_json'}",
            "Random bootloader message: rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)",
            "[1000] [INFO] [SYS ] Memory baseline check: 245000 bytes",
            "@FEATURES {\"frame_rate\":\"not_a_number\"}"
        ]
        for nl in noise_lines:
            self.parser.handle_line(nl)
        
        # None of the corrupt lines should break the parser
        self.assertEqual(self.parser.activity_count, 0)

if __name__ == '__main__':
    unittest.main()
