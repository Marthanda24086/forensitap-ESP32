#!/usr/bin/env python3
"""
ForensiTap-ESP32: Cryptographic Forensic Log Verifier & Audit Tool
Laptop-Side Verification Script (Stage 12)

Connects to the ForensiTap REST API (or parses exported log files),
recalculates every SHA-256 hash in the evidence chain from Genesis to tip,
detects tampering, modifications, deletions, or hash mismatches, and
generates a comprehensive forensic audit report.

Usage:
    python verify_logs.py --url http://192.168.1.26/api/logs
    python verify_logs.py --file forensitap_export.json
    python verify_logs.py --tamper-demo
"""

import argparse
import hashlib
import json
import sys
import urllib.request
import urllib.error

GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def build_canonical(index: int, timestamp_ms: int, event_type: str,
                    severity: str, description: str, prev_hash: str) -> str:
    return f"{index}|{timestamp_ms}|{event_type}|{severity}|{description}|{prev_hash}"

def verify_evidence_chain(chain_data: dict) -> dict:
    blocks = chain_data.get('blocks', [])
    if not blocks:
        return {
            'is_valid': False,
            'reason': 'No blocks present in evidence log payload',
            'blocks_checked': 0,
            'failed_index': None
        }

    total_blocks = len(blocks)
    for i, b in enumerate(blocks):
        idx = b.get('index', i)
        ts = b.get('timestamp_ms', 0)
        etype = b.get('event_type', '')
        sev = b.get('severity', '')
        desc = b.get('description', '')
        prev_h = b.get('prev_hash', '')
        block_h = b.get('block_hash', '')

        # 1. Genesis Check
        if idx == 0:
            if prev_h != GENESIS_PREV_HASH:
                return {
                    'is_valid': False,
                    'reason': f"Block #0 Genesis prev_hash invalid: expected all zeros, got {prev_h}",
                    'blocks_checked': i,
                    'failed_index': 0
                }
        elif i > 0:
            # 2. Hash Link Continuity
            prev_b = blocks[i - 1]
            expected_prev_hash = prev_b.get('block_hash', '')
            if prev_h != expected_prev_hash:
                return {
                    'is_valid': False,
                    'reason': f"Broken chain link at Block #{idx}: prev_hash does not match Block #{prev_b.get('index')}'s block_hash",
                    'blocks_checked': i,
                    'failed_index': idx
                }
            if idx != prev_b.get('index', 0) + 1:
                return {
                    'is_valid': False,
                    'reason': f"Sequence discontinuity between Block #{prev_b.get('index')} and #{idx}",
                    'blocks_checked': i,
                    'failed_index': idx
                }

        # 3. Cryptographic Hash Validation
        canonical = build_canonical(idx, ts, etype, sev, desc, prev_h)
        recalculated_hash = compute_sha256(canonical)

        if recalculated_hash != block_h:
            return {
                'is_valid': False,
                'reason': f"Tampering detected at Block #{idx}! Payload hash mismatch.\n  Expected: {recalculated_hash}\n  Recorded: {block_h}",
                'blocks_checked': i,
                'failed_index': idx
            }

    return {
        'is_valid': True,
        'reason': 'All cryptographic hashes and linkage verified successfully',
        'blocks_checked': total_blocks,
        'failed_index': None,
        'genesis_hash': blocks[0].get('block_hash', ''),
        'tip_hash': blocks[-1].get('block_hash', '')
    }

def print_audit_report(chain_data: dict, verification: dict):
    blocks = chain_data.get('blocks', [])
    print("=" * 76)
    print("       FORENSITAP-ESP32 CRYPTOGRAPHIC EVIDENCE CHAIN AUDIT REPORT")
    print("=" * 76)

    status_str = "[+] VERIFIED VALID (NO TAMPERING DETECTED)" if verification['is_valid'] else "[-] TAMPER DETECTED / INVALID CHAIN"
    print(f"Status           : {status_str}")
    print(f"Total Logged     : {chain_data.get('total_blocks', len(blocks))} blocks minted")
    print(f"Blocks Verified  : {verification['blocks_checked']} blocks inspected")
    if verification.get('genesis_hash'):
        print(f"Genesis Hash     : {verification['genesis_hash']}")
    if verification.get('tip_hash'):
        print(f"Chain Tip Hash   : {verification['tip_hash']}")
    print("-" * 76)

    print(f"Result Details   : {verification['reason']}")
    if not verification['is_valid']:
        print(f"Failed Block     : Block #{verification['failed_index']}")

    print("-" * 76)
    print("Recent Block Summary:")
    for b in blocks[-5:]:
        idx = b.get('index', 0)
        etype = b.get('event_type', '')
        sev = b.get('severity', '')
        desc = b.get('description', '')
        h_snippet = b.get('block_hash', '')[:16]
        print(f"  [#{idx:04d}][{sev:<6}][{etype:<20}] {desc[:30]:<30} | {h_snippet}...")
    print("=" * 76)

def run_tamper_demo():
    print("[*] Running simulated adversary tamper demonstration...")
    # Create benign chain of 3 blocks
    blocks = []
    g_canon = build_canonical(0, 100, "SYSTEM_BOOT", "INFO", "Genesis block", GENESIS_PREV_HASH)
    g_hash = compute_sha256(g_canon)
    blocks.append({'index': 0, 'timestamp_ms': 100, 'event_type': 'SYSTEM_BOOT', 'severity': 'INFO', 'description': 'Genesis block', 'prev_hash': GENESIS_PREV_HASH, 'block_hash': g_hash})

    b1_canon = build_canonical(1, 1500, "NEW_DEVICE_OBSERVED", "INFO", "Device: 42:CF:AA:4B:B3:45", g_hash)
    b1_hash = compute_sha256(b1_canon)
    blocks.append({'index': 1, 'timestamp_ms': 1500, 'event_type': 'NEW_DEVICE_OBSERVED', 'severity': 'INFO', 'description': 'Device: 42:CF:AA:4B:B3:45', 'prev_hash': g_hash, 'block_hash': b1_hash})

    b2_canon = build_canonical(2, 3500, "TRAFFIC_SPIKE", "MEDIUM", "Traffic spike: 208.1 fps", b1_hash)
    b2_hash = compute_sha256(b2_canon)
    blocks.append({'index': 2, 'timestamp_ms': 3500, 'event_type': 'TRAFFIC_SPIKE', 'severity': 'MEDIUM', 'description': 'Traffic spike: 208.1 fps', 'prev_hash': b1_hash, 'block_hash': b2_hash})

    chain_payload = {'total_blocks': 3, 'blocks': blocks}
    initial_ver = verify_evidence_chain(chain_payload)
    print(f"[*] Initial Authentic Chain Verification: {'PASSED' if initial_ver['is_valid'] else 'FAILED'}")

    # Adversary attempts to alter block 1's description to conceal evidence
    print("[!] Attacker modifies Block #1 payload (altering observed MAC address)...")
    blocks[1]['description'] = "Device: 00:00:00:00:00:00"
    tampered_ver = verify_evidence_chain(chain_payload)
    print_audit_report(chain_payload, tampered_ver)

def main():
    parser = argparse.ArgumentParser(description="ForensiTap-ESP32 Forensic Log Audit Tool")
    parser.add_argument("--url", default="http://192.168.1.26/api/logs", help="ESP32 /api/logs URL")
    parser.add_argument("--file", help="Path to exported logs JSON file")
    parser.add_argument("--tamper-demo", action="store_true", help="Execute simulation demonstrating tamper detection")
    args = parser.parse_args()

    if args.tamper_demo:
        run_tamper_demo()
        return

    if args.file:
        try:
            with open(args.file, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[-] Error reading file {args.file}: {e}")
            sys.exit(1)
    else:
        print(f"[*] Fetching evidence chain from {args.url} ...")
        try:
            req = urllib.request.Request(args.url, headers={'User-Agent': 'ForensiTapAudit/1.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as e:
            print(f"[-] Connection failed: {e}")
            print("[*] (Ensure ESP32 is powered on and laptop is on the same Wi-Fi network)")
            sys.exit(1)

    res = verify_evidence_chain(data)
    print_audit_report(data, res)
    if not res['is_valid']:
        sys.exit(2)

if __name__ == '__main__':
    main()
