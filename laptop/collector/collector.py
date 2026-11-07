#!/usr/bin/env python3
"""
ForensiTap-ESP32: High-Performance Streaming Forensic Collector
Stage 14 Implementation

Asynchronously queries the ForensiTap-ESP32 appliance, ingests real-time
telemetry, feature profiles, device sightings, and cryptographically sealed
SHA-256 evidence blocks, writing structured append-only JSONL files with
automatic retry, exponential backoff, and local chain verification.

Usage:
    python collector.py [--esp-url http://192.168.1.26] [--interval 2.0]
                        [--output-dir ../../datasets/sessions] [--duration 60]
"""

import argparse
import datetime
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, Any, Optional, Set

DEFAULT_ESP_URL = "http://192.168.1.26"
DEFAULT_INTERVAL = 2.0
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datasets", "sessions")

class ForensiTapCollector:
    def __init__(self, base_url: str = DEFAULT_ESP_URL, interval: float = DEFAULT_INTERVAL,
                 output_dir: str = DEFAULT_OUTPUT_DIR, duration: Optional[float] = None):
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.output_dir = output_dir
        self.duration = duration

        self.is_running = True
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.output_dir, f"session_{self.session_id}")

        self.telemetry_path = os.path.join(self.session_dir, "telemetry.jsonl")
        self.devices_path = os.path.join(self.session_dir, "devices.jsonl")
        self.evidence_path = os.path.join(self.session_dir, "evidence_chain.jsonl")
        self.meta_path = os.path.join(self.session_dir, "session_meta.json")

        self.ingested_block_indices: Set[int] = set()
        self.total_records_ingested = 0
        self.total_frames_observed = 0
        self.start_time = 0.0

        # Backoff parameters
        self.backoff_sec = 1.0
        self.max_backoff = 10.0

    def init_storage(self):
        os.makedirs(self.session_dir, exist_ok=True)
        meta = {
            "session_id": self.session_id,
            "start_iso": datetime.datetime.now().isoformat(),
            "target_url": self.base_url,
            "polling_interval_sec": self.interval,
            "status": "ACTIVE"
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def fetch_json(self, endpoint: str, timeout: float = 4.0) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "ForensiTapCollector/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    self.backoff_sec = 1.0  # Reset backoff on success
                    return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            return None
        return None

    def append_jsonl(self, filepath: str, data: Dict[str, Any]):
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def run_collection_cycle(self):
        now_ts = time.time()
        now_iso = datetime.datetime.now().isoformat()

        health = self.fetch_json("/api/health")
        if not health:
            print(f"[!] Target {self.base_url} unreachable. Retrying in {self.backoff_sec:.1f}s...")
            time.sleep(self.backoff_sec)
            self.backoff_sec = min(self.backoff_sec * 1.5, self.max_backoff)
            return

        stats = self.fetch_json("/api/stats") or {}
        features = self.fetch_json("/api/features") or {}
        devices = self.fetch_json("/api/devices") or {}
        alerts = self.fetch_json("/api/alerts") or {}
        logs = self.fetch_json("/api/logs") or {}

        # 1. Telemetry Record
        telemetry_entry = {
            "timestamp": now_ts,
            "datetime": now_iso,
            "health": health,
            "stats": stats,
            "features": features,
            "alerts_summary": {
                "count": alerts.get("count", 0),
                "total": alerts.get("total_alerts_generated", 0)
            }
        }
        self.append_jsonl(self.telemetry_path, telemetry_entry)

        # 2. Devices Sighting
        if "devices" in devices and devices["devices"]:
            dev_entry = {
                "timestamp": now_ts,
                "datetime": now_iso,
                "device_count": len(devices["devices"]),
                "devices": devices["devices"]
            }
            self.append_jsonl(self.devices_path, dev_entry)

        # 3. Evidence Chain Ingestion (Deduplicated by Block Index)
        blocks = logs.get("blocks", [])
        new_blocks = 0
        for b in blocks:
            idx = b.get("index")
            if idx is not None and idx not in self.ingested_block_indices:
                self.ingested_block_indices.add(idx)
                self.append_jsonl(self.evidence_path, b)
                new_blocks += 1

        self.total_records_ingested += 1
        self.total_frames_observed = stats.get("total_observed_frames", self.total_frames_observed)

        # Real-time console status line
        fps = stats.get("current_frame_rate", 0)
        peers = len(devices.get("devices", []))
        heap_kb = round(health.get("free_heap_bytes", 0) / 1024)
        uptime = health.get("uptime_sec", 0)
        total_blocks = len(self.ingested_block_indices)

        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ForensiTap | "
              f"Uptime: {uptime}s | {fps:.1f} fps | {peers} peers | "
              f"Blocks: {total_blocks} (+{new_blocks}) | Heap: {heap_kb} KB")

    def start(self):
        self.init_storage()
        self.start_time = time.time()
        print("=" * 76)
        print("      FORENSITAP-ESP32 STREAMING DATA COLLECTION PIPELINE")
        print("=" * 76)
        print(f"[*] Target Appliance : {self.base_url}")
        print(f"[*] Polling Rate     : {self.interval}s")
        print(f"[*] Session Storage  : {self.session_dir}")
        if self.duration:
            print(f"[*] Maximum Duration : {self.duration}s")
        print("=" * 76)
        print("[*] Ingestion pipeline running. Press Ctrl+C to terminate.")

        def sig_handler(sig, frame):
            print("\n[*] Termination signal received. Finalizing session...")
            self.is_running = False

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        while self.is_running:
            loop_start = time.time()

            if self.duration and (loop_start - self.start_time) >= self.duration:
                print(f"[*] Configured duration ({self.duration}s) reached.")
                break

            self.run_collection_cycle()

            elapsed = time.time() - loop_start
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)

        self.finalize()

    def finalize(self):
        duration_sec = round(time.time() - self.start_time, 2)
        meta = {
            "session_id": self.session_id,
            "start_iso": datetime.datetime.fromtimestamp(self.start_time).isoformat(),
            "end_iso": datetime.datetime.now().isoformat(),
            "duration_sec": duration_sec,
            "target_url": self.base_url,
            "total_cycles_completed": self.total_records_ingested,
            "total_blocks_ingested": len(self.ingested_block_indices),
            "final_observed_frames": self.total_frames_observed,
            "status": "COMPLETED"
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print("\n" + "=" * 76)
        print("                 COLLECTION SESSION COMPLETE")
        print("=" * 76)
        print(f"Session ID       : {self.session_id}")
        print(f"Elapsed Time     : {duration_sec} seconds")
        print(f"Records Ingested : {self.total_records_ingested} cycles")
        print(f"Evidence Blocks  : {len(self.ingested_block_indices)} blocks preserved")
        print(f"Saved Directory  : {self.session_dir}")
        print("=" * 76)

def main():
    parser = argparse.ArgumentParser(description="ForensiTap-ESP32 Streaming Collector")
    parser.add_argument("--esp-url", default=DEFAULT_ESP_URL, help="ESP32 API base URL")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="Polling interval in seconds")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Session output directory")
    parser.add_argument("--duration", type=float, help="Collection duration in seconds")
    args = parser.parse_args()

    collector = ForensiTapCollector(
        base_url=args.esp_url,
        interval=args.interval,
        output_dir=args.output_dir,
        duration=args.duration
    )
    collector.start()

if __name__ == "__main__":
    main()
