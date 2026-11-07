#!/usr/bin/env python3
"""
ForensiTap-ESP32: SHA-256 Tamper-Evident Evidence Logger Unit Tests
Validates genesis block generation, sequential cryptographic chaining,
tamper detection (payload and hash tampering), and sliding window integrity.
"""

import hashlib
import unittest
from typing import List, Optional

GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def build_canonical(index: int, timestamp_ms: int, event_type: str,
                    severity: str, description: str, prev_hash: str) -> str:
    return f"{index}|{timestamp_ms}|{event_type}|{severity}|{description}|{prev_hash}"

class EvidenceBlock:
    def __init__(self, index: int, timestamp_ms: int, event_type: str,
                 severity: str, description: str, prev_hash: str, block_hash: str):
        self.index = index
        self.timestamp_ms = timestamp_ms
        self.event_type = event_type
        self.severity = severity
        self.description = description
        self.prev_hash = prev_hash
        self.block_hash = block_hash

class EvidenceLoggerSimulator:
    MAX_BLOCKS = 32

    def __init__(self):
        self.blocks: List[EvidenceBlock] = []
        self.total_blocks = 0
        self.genesis_hash = ""
        self.tip_hash = ""
        self.mint_genesis()

    def mint_genesis(self):
        canonical = build_canonical(0, 100, "SYSTEM_BOOT", "INFO",
                                    "Genesis block: ForensiTap evidence chain initialized",
                                    GENESIS_PREV_HASH)
        bhash = compute_sha256(canonical)
        block = EvidenceBlock(0, 100, "SYSTEM_BOOT", "INFO",
                              "Genesis block: ForensiTap evidence chain initialized",
                              GENESIS_PREV_HASH, bhash)
        self.blocks.append(block)
        self.total_blocks = 1
        self.genesis_hash = bhash
        self.tip_hash = bhash

    def log_evidence(self, timestamp_ms: int, event_type: str, severity: str, description: str) -> EvidenceBlock:
        next_idx = self.total_blocks
        prev_h = self.tip_hash

        canonical = build_canonical(next_idx, timestamp_ms, event_type, severity, description, prev_h)
        bhash = compute_sha256(canonical)

        block = EvidenceBlock(next_idx, timestamp_ms, event_type, severity, description, prev_h, bhash)

        if len(self.blocks) < self.MAX_BLOCKS:
            self.blocks.append(block)
        else:
            self.blocks.pop(0)
            self.blocks.append(block)

        self.tip_hash = bhash
        self.total_blocks += 1
        return block

    def verify_chain(self) -> (bool, Optional[int], str):
        if not self.blocks:
            return False, None, "Empty chain"

        for i, b in enumerate(self.blocks):
            if b.index == 0:
                if b.prev_hash != GENESIS_PREV_HASH:
                    return False, 0, "Genesis prev_hash invalid"
            elif i > 0:
                prev = self.blocks[i - 1]
                if b.index != prev.index + 1:
                    return False, b.index, f"Discontinuous sequence between {prev.index} and {b.index}"
                if b.prev_hash != prev.block_hash:
                    return False, b.index, f"Broken link: block {b.index} prev_hash != block {prev.index} hash"

            expected_canonical = build_canonical(b.index, b.timestamp_ms, b.event_type,
                                                 b.severity, b.description, b.prev_hash)
            expected_hash = compute_sha256(expected_canonical)
            if expected_hash != b.block_hash:
                return False, b.index, f"Digest mismatch at index {b.index} (Tampered)"

        return True, None, "Chain Verified Valid"


class TestEvidenceLogger(unittest.TestCase):
    def setUp(self):
        self.logger = EvidenceLoggerSimulator()

    def test_genesis_block(self):
        self.assertEqual(len(self.logger.blocks), 1)
        self.assertEqual(self.logger.total_blocks, 1)
        g = self.logger.blocks[0]
        self.assertEqual(g.index, 0)
        self.assertEqual(g.prev_hash, GENESIS_PREV_HASH)
        self.assertEqual(len(g.block_hash), 64)
        valid, failed_idx, msg = self.logger.verify_chain()
        self.assertTrue(valid)

    def test_sequential_chaining(self):
        self.logger.log_evidence(1000, "NEW_DEVICE_OBSERVED", "INFO", "Station discovered: 42:CF:AA:4B:B3:45")
        self.logger.log_evidence(2000, "TRAFFIC_SPIKE", "MEDIUM", "Traffic spike: 208.1 fps")
        self.logger.log_evidence(3000, "MGMT_FRAME_FLOOD", "WARNING", "Excessive mgmt frames: 68.2%")

        self.assertEqual(len(self.logger.blocks), 4) # Genesis + 3
        self.assertEqual(self.logger.total_blocks, 4)

        # Verify hash link chaining
        for i in range(1, len(self.logger.blocks)):
            self.assertEqual(self.logger.blocks[i].prev_hash, self.logger.blocks[i-1].block_hash)

        valid, failed_idx, msg = self.logger.verify_chain()
        self.assertTrue(valid)
        self.assertEqual(msg, "Chain Verified Valid")

    def test_tamper_payload_detection(self):
        self.logger.log_evidence(1000, "TRAFFIC_SPIKE", "MEDIUM", "Traffic spike: 208.1 fps")
        self.logger.log_evidence(2000, "NEW_DEVICE_OBSERVED", "INFO", "Device: 42:CF:AA:4B:B3:45")

        # Adversary attempts to alter block 1 description
        self.logger.blocks[1].description = "Normal traffic: 50.0 fps"

        valid, failed_idx, msg = self.logger.verify_chain()
        self.assertFalse(valid)
        self.assertEqual(failed_idx, 1)
        self.assertIn("Digest mismatch", msg)

    def test_tamper_prev_hash_detection(self):
        self.logger.log_evidence(1000, "TRAFFIC_SPIKE", "MEDIUM", "Traffic spike: 208.1 fps")
        self.logger.log_evidence(2000, "NEW_DEVICE_OBSERVED", "INFO", "Device: 42:CF:AA:4B:B3:45")

        # Adversary attempts to change prev_hash of block 2
        self.logger.blocks[2].prev_hash = "1111111111111111111111111111111111111111111111111111111111111111"

        valid, failed_idx, msg = self.logger.verify_chain()
        self.assertFalse(valid)
        self.assertEqual(failed_idx, 2)

    def test_window_fifo_eviction(self):
        # Mint 40 blocks (capacity is 32)
        for i in range(1, 41):
            self.logger.log_evidence(i * 1000, "DEVICE", "INFO", f"Device #{i}")

        self.assertEqual(len(self.logger.blocks), 32)
        self.assertEqual(self.logger.total_blocks, 41)

        # Remaining 32 blocks should still verify as internally linked
        valid, failed_idx, msg = self.logger.verify_chain()
        self.assertTrue(valid)

if __name__ == '__main__':
    unittest.main()
