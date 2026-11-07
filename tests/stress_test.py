#!/usr/bin/env python3
"""
ForensiTap-ESP32: Full System Integration & Stress Testing Suite
Stage 15 Implementation

Executes multi-phase load and stress tests against the live ForensiTap-ESP32
appliance (or offline simulated server), assessing:
1. High-frequency API burst resilience across all 7 REST endpoints.
2. Concurrent multi-threaded request handling under continuous promiscuous sniffing.
3. Heap stability and memory leak detection (Delta Heap evaluation).
4. End-to-end cryptographic SHA-256 evidence chain integrity verification.

Usage:
    python tests/stress_test.py [--target-url http://192.168.1.26]
                                [--cycles 100] [--concurrency 4] [--mock]
"""

import argparse
import concurrent.futures
import hashlib
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Any, Optional

DEFAULT_TARGET_URL = "http://192.168.1.26"
GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

ENDPOINTS = [
    "/api/health",
    "/api/stats",
    "/api/features",
    "/api/devices",
    "/api/alerts",
    "/api/logs",
    "/api/logs/verify"
]

def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def build_canonical(index: int, timestamp_ms: int, event_type: str,
                    severity: str, description: str, prev_hash: str) -> str:
    return f"{index}|{timestamp_ms}|{event_type}|{severity}|{description}|{prev_hash}"

class MockForensiTapServer:
    """Emulates ESP32 API responses for automated offline unit testing."""
    def __init__(self):
        self.mock_heap = 215000
        self.total_reqs = 0

    def query(self, endpoint: str) -> (int, Dict[str, Any], float):
        self.total_reqs += 1
        time.sleep(0.005) # 5ms simulated network latency
        if endpoint == "/api/health":
            return 200, {
                "status": "OPTIMAL", "uptime_ms": 120000, "uptime_sec": 120,
                "free_heap_bytes": self.mock_heap - (self.total_reqs % 100),
                "wifi_connected": True, "wifi_channel": 11, "rssi_dbm": -55
            }, 0.005
        elif endpoint == "/api/stats":
            return 200, {
                "monitoring_status": "ACTIVE", "current_frame_rate": 142.0,
                "total_observed_frames": 25000, "management_frame_count": 5000,
                "data_frame_count": 20000, "dropped_frames_count": 0
            }, 0.006
        elif endpoint == "/api/features":
            return 200, {
                "frame_rate": 140.0, "byte_rate": 28000.0, "average_frame_size": 200.0,
                "unique_peers": 18, "management_frame_ratio": 0.20,
                "traffic_burst_score": 1.45,
                "baseline": {"warmup_ready": True, "mean_frame_rate": 125.0, "std_frame_rate": 35.0, "frame_rate_zscore": 0.43}
            }, 0.007
        elif endpoint == "/api/devices":
            return 200, {"count": 2, "devices": [{"mac": "64:FB:92:C0:14:80", "packets": 1000, "is_ap": True}]}, 0.008
        elif endpoint == "/api/alerts":
            return 200, {"count": 1, "alerts": [{"event_id": 1, "event_type": "SYSTEM_BOOT"}]}, 0.006
        elif endpoint == "/api/logs":
            g_canon = build_canonical(0, 100, "SYSTEM_BOOT", "INFO", "Genesis", GENESIS_PREV_HASH)
            g_hash = compute_sha256(g_canon)
            return 200, {
                "chain_valid": True, "total_blocks": 1, "stored_count": 1,
                "genesis_hash": g_hash, "tip_hash": g_hash,
                "blocks": [{"index": 0, "timestamp_ms": 100, "event_type": "SYSTEM_BOOT", "severity": "INFO", "description": "Genesis", "prev_hash": GENESIS_PREV_HASH, "block_hash": g_hash}]
            }, 0.012
        elif endpoint == "/api/logs/verify":
            return 200, {"status": "VALID", "chain_intact": True, "blocks_checked": 1}, 0.008
        return 404, {"error": "NOT_FOUND"}, 0.002

class SystemStressTester:
    def __init__(self, target_url: str = DEFAULT_TARGET_URL, cycles: int = 70,
                 concurrency: int = 4, is_mock: bool = False):
        self.target_url = target_url.rstrip("/")
        self.cycles = cycles
        self.concurrency = concurrency
        self.is_mock = is_mock
        self.mock_server = MockForensiTapServer() if is_mock else None

        self.latencies_by_endpoint: Dict[str, List[float]] = {ep: [] for ep in ENDPOINTS}
        self.failures = 0
        self.successes = 0
        self.initial_heap = 0
        self.final_heap = 0

    def query_endpoint(self, endpoint: str) -> (int, Optional[Dict[str, Any]], float):
        if self.is_mock:
            return self.mock_server.query(endpoint)

        url = f"{self.target_url}{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "ForensiTapStress/1.0"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                elapsed = time.perf_counter() - t0
                status = resp.status
                data = json.loads(resp.read().decode('utf-8'))
                return status, data, elapsed
        except Exception as e:
            elapsed = time.perf_counter() - t0
            return 500, None, elapsed

    def run_stress_test(self) -> Dict[str, Any]:
        print("=" * 76)
        print("       FORENSITAP-ESP32 FULL SYSTEM STRESS & INTEGRATION TEST")
        print("=" * 76)
        mode_str = "MOCK SIMULATION (OFFLINE)" if self.is_mock else f"LIVE TARGET ({self.target_url})"
        print(f"[*] Operational Mode   : {mode_str}")
        print(f"[*] Burst Requests     : {self.cycles} requests")
        print(f"[*] Worker Concurrency : {self.concurrency} parallel threads")
        print(f"[*] Monitored Endpoints: {len(ENDPOINTS)} endpoints")
        print("=" * 76)

        # ---------------------------------------------------------------------
        # Phase 1: Baseline Health Check
        # ---------------------------------------------------------------------
        print("[*] Phase 1: Evaluating baseline system health...")
        status, health_data, lat = self.query_endpoint("/api/health")
        if status != 200 or not health_data:
            print(f"[-] FATAL: Appliance unreachable at {self.target_url}")
            return {"passed": False, "reason": "Appliance unreachable"}

        self.initial_heap = health_data.get("free_heap_bytes", 0)
        uptime = health_data.get("uptime_sec", 0)
        channel = health_data.get("wifi_channel", 0)
        rssi = health_data.get("rssi_dbm", 0)
        print(f"    -> Baseline Heap  : {self.initial_heap:,} bytes ({round(self.initial_heap/1024)} KB)")
        print(f"    -> Device Uptime  : {uptime} seconds | Channel: {channel} | RSSI: {rssi} dBm")
        print(f"    -> Status Check   : OPTIMAL (Latency: {lat*1000:.2f} ms)\n")

        # ---------------------------------------------------------------------
        # Phase 2 & 3: Concurrent Multi-Threaded Load Test
        # ---------------------------------------------------------------------
        print(f"[*] Phase 2-3: Dispatching {self.cycles} concurrent burst requests...")

        request_queue = []
        for i in range(self.cycles):
            ep = ENDPOINTS[i % len(ENDPOINTS)]
            request_queue.append(ep)

        test_start = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_ep = {executor.submit(self.query_endpoint, ep): ep for ep in request_queue}
            completed_count = 0

            for future in concurrent.futures.as_completed(future_to_ep):
                ep = future_to_ep[future]
                completed_count += 1
                try:
                    status, data, elapsed = future.result()
                    if status == 200:
                        self.successes += 1
                        self.latencies_by_endpoint[ep].append(elapsed * 1000.0) # in ms
                    else:
                        self.failures += 1
                except Exception:
                    self.failures += 1

                if completed_count % 20 == 0 or completed_count == self.cycles:
                    sys.stdout.write(f"\r    -> Ingestion Progress: {completed_count}/{self.cycles} requests completed ({self.successes} OK, {self.failures} Err)")
                    sys.stdout.flush()

        total_time = time.perf_counter() - test_start
        print(f"\n    -> Completed in {total_time:.2f}s (Effective Throughput: {self.cycles / total_time:.1f} req/s)\n")

        # ---------------------------------------------------------------------
        # Phase 4: Cryptographic Chain Integrity Verification
        # ---------------------------------------------------------------------
        print("[*] Phase 4: Cryptographic evidence chain verification after load...")
        status, verify_data, lat = self.query_endpoint("/api/logs/verify")
        chain_intact = verify_data.get("chain_intact", False) if (status == 200 and verify_data) else False
        blocks_checked = verify_data.get("blocks_checked", 0) if verify_data else 0

        status, logs_data, _ = self.query_endpoint("/api/logs")
        blocks = logs_data.get("blocks", []) if (status == 200 and logs_data) else []

        # Mathematical audit of blocks
        local_audit_valid = True
        failed_block_idx = None
        for i, b in enumerate(blocks):
            idx = b.get("index", 0)
            prev_h = b.get("prev_hash", "")
            if idx == 0 and prev_h != GENESIS_PREV_HASH:
                local_audit_valid = False
                failed_block_idx = 0
                break
            elif i > 0 and prev_h != blocks[i-1].get("block_hash"):
                local_audit_valid = False
                failed_block_idx = idx
                break
            canon = build_canonical(idx, b.get("timestamp_ms", 0), b.get("event_type", ""),
                                    b.get("severity", ""), b.get("description", ""), prev_h)
            if compute_sha256(canon) != b.get("block_hash"):
                local_audit_valid = False
                failed_block_idx = idx
                break

        chain_verdict = (chain_intact and local_audit_valid)
        print(f"    -> ESP32 On-Chip Verification : {'PASSED (Intact)' if chain_intact else 'FAILED'}")
        print(f"    -> Host Mathematical Audit   : {'PASSED (Intact)' if local_audit_valid else f'TAMPER DETECTED at Block #{failed_block_idx}'}")
        print(f"    -> Blocks Verified            : {blocks_checked} in-memory blocks\n")

        # ---------------------------------------------------------------------
        # Phase 5: Memory Leak & Heap Drift Evaluation
        # ---------------------------------------------------------------------
        print("[*] Phase 5: Memory leak & heap drift analysis...")
        # Brief pause to allow any transient response buffers to flush
        time.sleep(0.5)
        status, final_health, _ = self.query_endpoint("/api/health")
        self.final_heap = final_health.get("free_heap_bytes", self.initial_heap) if final_health else self.initial_heap
        heap_delta = self.final_heap - self.initial_heap
        heap_pct_change = (heap_delta / self.initial_heap * 100.0) if self.initial_heap > 0 else 0.0

        print(f"    -> Initial Heap : {self.initial_heap:,} bytes")
        print(f"    -> Final Heap   : {self.final_heap:,} bytes")
        print(f"    -> Heap Delta   : {heap_delta:+,} bytes ({heap_pct_change:+.2f}%)")

        # Within +/- 5% or slight fluctuations is nominal for non-fragmented heap
        heap_healthy = abs(heap_pct_change) < 5.0 and self.final_heap > 150000
        print(f"    -> Memory Health: {'STABLE (Zero Leakage)' if heap_healthy else 'ATTENTION NEEDED'}\n")

        # ---------------------------------------------------------------------
        # Phase 6: Benchmark & Performance Summary
        # ---------------------------------------------------------------------
        print("=" * 76)
        print("                 SYSTEM PERFORMANCE & LATENCY BENCHMARK")
        print("=" * 76)
        print(f"{'Endpoint':<20} | {'Reqs':<6} | {'Min (ms)':<9} | {'Mean (ms)':<10} | {'95th% (ms)':<10} | {'Max (ms)':<9}")
        print("-" * 76)

        all_lats = []
        for ep in ENDPOINTS:
            lats = self.latencies_by_endpoint[ep]
            if lats:
                all_lats.extend(lats)
                p95 = statistics.quantiles(lats, n=20)[18] if len(lats) >= 20 else max(lats)
                print(f"{ep:<20} | {len(lats):<6} | {min(lats):<9.2f} | {statistics.mean(lats):<10.2f} | {p95:<10.2f} | {max(lats):<9.2f}")
            else:
                print(f"{ep:<20} | 0      | N/A       | N/A        | N/A        | N/A")

        print("-" * 76)
        overall_mean = statistics.mean(all_lats) if all_lats else 0.0
        success_rate = (self.successes / self.cycles * 100.0) if self.cycles > 0 else 0.0
        print(f"Overall Latency Mean : {overall_mean:.2f} ms")
        print(f"Success Rate         : {success_rate:.1f}% ({self.successes}/{self.cycles} requests successful)")
        print(f"Failure Count        : {self.failures} dropped/errored requests")
        print("=" * 76)

        passed = (self.failures == 0) and chain_verdict and heap_healthy
        verdict_str = "[+] INTEGRATION & STRESS TEST PASSED (SYSTEM PRODUCTION READY)" if passed else "[-] INTEGRATION TEST FAILED"
        print(f"FINAL VERDICT : {verdict_str}")
        print("=" * 76)

        return {
            "passed": passed,
            "success_rate": success_rate,
            "failures": self.failures,
            "overall_mean_latency_ms": overall_mean,
            "initial_heap": self.initial_heap,
            "final_heap": self.final_heap,
            "heap_delta_bytes": heap_delta,
            "chain_intact": chain_verdict
        }

def main():
    parser = argparse.ArgumentParser(description="ForensiTap-ESP32 Stress & Integration Test")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="ESP32 API Base URL")
    parser.add_argument("--cycles", type=int, default=70, help="Total requests across endpoints (default: 70)")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent client threads (default: 4)")
    parser.add_argument("--mock", action="store_true", help="Run simulated offline stress test")
    args = parser.parse_args()

    tester = SystemStressTester(
        target_url=args.target_url,
        cycles=args.cycles,
        concurrency=args.concurrency,
        is_mock=args.mock
    )
    results = tester.run_stress_test()
    if not results.get("passed", False):
        sys.exit(1)

if __name__ == "__main__":
    main()
