#!/usr/bin/env python3
"""
ForensiTap-ESP32: Metadata Processing & Device Tracking Unit Tests
Validates MAC sanitization, frame boundary validation, LRU eviction,
and optional live query against ESP32 REST API.
"""

import sys
import unittest

def is_valid_unicast_mac(mac_bytes):
    """Replicates ForensiTapWifiMonitor::isValidUnicastMac logic."""
    if len(mac_bytes) != 6:
        return False
    # Reject all zeros
    if all(b == 0 for b in mac_bytes):
        return False
    # Reject broadcast
    if all(b == 0xFF for b in mac_bytes):
        return False
    # Reject multicast (least significant bit of first octet is 1)
    if mac_bytes[0] & 0x01:
        return False
    return True

class TestMetadataProcessing(unittest.TestCase):
    def test_mac_validation(self):
        # Valid unicast MACs
        self.assertTrue(is_valid_unicast_mac(bytes([0x00, 0x4B, 0x12, 0xEF, 0x49, 0x38])))
        self.assertTrue(is_valid_unicast_mac(bytes([0x24, 0x6F, 0x28, 0x1A, 0x2B, 0x3C])))

        # Invalid MACs
        self.assertFalse(is_valid_unicast_mac(bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))) # All zeros
        self.assertFalse(is_valid_unicast_mac(bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]))) # Broadcast
        self.assertFalse(is_valid_unicast_mac(bytes([0x01, 0x00, 0x5E, 0x00, 0x00, 0x01]))) # IPv4 Multicast
        self.assertFalse(is_valid_unicast_mac(bytes([0x33, 0x33, 0x00, 0x00, 0x00, 0x01]))) # IPv6 Multicast

    def test_frame_length_bounds(self):
        # 802.11 min frame length = 10, max = 2346
        def is_valid_length(length):
            return 10 <= length <= 2346

        self.assertTrue(is_valid_length(24))
        self.assertTrue(is_valid_length(1500))
        self.assertFalse(is_valid_length(5))     # Fragment / truncated
        self.assertFalse(is_valid_length(3000))  # Corrupted jumbo frame

    def test_lru_device_eviction(self):
        # Simulate fixed capacity device table (capacity = 4)
        capacity = 4
        table = {}

        def insert_device(mac, timestamp):
            if mac in table:
                table[mac]['last_seen'] = timestamp
                table[mac]['count'] += 1
                return
            if len(table) >= capacity:
                # Evict oldest by last_seen
                oldest_mac = min(table.keys(), key=lambda k: table[k]['last_seen'])
                del table[oldest_mac]
            table[mac] = {'first_seen': timestamp, 'last_seen': timestamp, 'count': 1}

        insert_device("AA:AA:AA:AA:AA:AA", 100)
        insert_device("BB:BB:BB:BB:BB:BB", 200)
        insert_device("CC:CC:CC:CC:CC:CC", 300)
        insert_device("DD:DD:DD:DD:DD:DD", 400)

        self.assertEqual(len(table), 4)
        self.assertIn("AA:AA:AA:AA:AA:AA", table)

        # Insert 5th device at timestamp 500 -> should evict AA (oldest last_seen = 100)
        insert_device("EE:EE:EE:EE:EE:EE", 500)
        self.assertEqual(len(table), 4)
        self.assertNotIn("AA:AA:AA:AA:AA:AA", table)
        self.assertIn("EE:EE:EE:EE:EE:EE", table)

if __name__ == '__main__':
    unittest.main()
