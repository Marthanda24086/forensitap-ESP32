#!/usr/bin/env python3
"""
ForensiTap-ESP32: Offline Forensic Traffic Analytics Engine
Stage 14 Implementation

Processes session logs captured by ForensiTapCollector, performing deep
traffic distribution analysis, frame composition breakdown, device flow
profiling, anomaly event clustering, and cryptographic chain auditing.

Usage:
    python traffic_analysis.py [--session-dir ../../datasets/sessions/session_...]
                               [--latest] [--export-json]
"""

import argparse
import glob
import hashlib
import json
import math
import os
import statistics
import sys
from typing import Dict, List, Any, Optional

GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def build_canonical(index: int, timestamp_ms: int, event_type: str,
                    severity: str, description: str, prev_hash: str) -> str:
    return f"{index}|{timestamp_ms}|{event_type}|{severity}|{description}|{prev_hash}"

class ForensicTrafficAnalyzer:
    def __init__(self, session_dir: str):
        self.session_dir = os.path.abspath(session_dir)
        self.telemetry_path = os.path.join(self.session_dir, "telemetry.jsonl")
        self.devices_path = os.path.join(self.session_dir, "devices.jsonl")
        self.evidence_path = os.path.join(self.session_dir, "evidence_chain.jsonl")
        self.meta_path = os.path.join(self.session_dir, "session_meta.json")

        self.telemetry_records: List[Dict[str, Any]] = []
        self.device_snapshots: List[Dict[str, Any]] = []
        self.evidence_blocks: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {}

    def load_data(self) -> bool:
        if not os.path.isdir(self.session_dir):
            print(f"[-] Session directory not found: {self.session_dir}")
            return False

        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.meta = json.load(f)

        if os.path.exists(self.telemetry_path):
            with open(self.telemetry_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.telemetry_records.append(json.loads(line))

        if os.path.exists(self.devices_path):
            with open(self.devices_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.device_snapshots.append(json.loads(line))

        if os.path.exists(self.evidence_path):
            with open(self.evidence_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.evidence_blocks.append(json.loads(line))

        return len(self.telemetry_records) > 0 or len(self.evidence_blocks) > 0

    def analyze_throughput(self) -> Dict[str, Any]:
        fps_samples = []
        byte_rate_samples = []
        mgmt_ratio_samples = []
        burst_samples = []
        mgmt_frames = 0
        data_frames = 0
        total_observed = 0
        dropped_frames = 0

        for r in self.telemetry_records:
            stats = r.get("stats", {})
            feat = r.get("features", {})

            fps = stats.get("current_frame_rate", feat.get("frame_rate", 0))
            if fps is not None:
                fps_samples.append(float(fps))

            br = feat.get("byte_rate")
            if br is not None:
                byte_rate_samples.append(float(br))

            mr = feat.get("management_frame_ratio")
            if mr is not None:
                mgmt_ratio_samples.append(float(mr))

            bs = feat.get("traffic_burst_score")
            if bs is not None:
                burst_samples.append(float(bs))

            mgmt_frames = max(mgmt_frames, stats.get("management_frame_count", 0))
            data_frames = max(data_frames, stats.get("data_frame_count", 0))
            total_observed = max(total_observed, stats.get("total_observed_frames", 0))
            dropped_frames = max(dropped_frames, stats.get("dropped_frames_count", 0))

        if not fps_samples:
            return {"samples": 0}

        return {
            "samples": len(fps_samples),
            "fps_min": min(fps_samples),
            "fps_max": max(fps_samples),
            "fps_mean": statistics.mean(fps_samples),
            "fps_median": statistics.median(fps_samples),
            "fps_std": statistics.stdev(fps_samples) if len(fps_samples) > 1 else 0.0,
            "byte_rate_mean_kbs": (statistics.mean(byte_rate_samples) / 1024) if byte_rate_samples else 0.0,
            "byte_rate_peak_kbs": (max(byte_rate_samples) / 1024) if byte_rate_samples else 0.0,
            "mgmt_ratio_mean": statistics.mean(mgmt_ratio_samples) if mgmt_ratio_samples else 0.0,
            "burst_score_max": max(burst_samples) if burst_samples else 1.0,
            "total_observed_frames": total_observed,
            "management_frames": mgmt_frames,
            "data_frames": data_frames,
            "dropped_frames": dropped_frames
        }

    def analyze_devices(self) -> Dict[str, Any]:
        device_map: Dict[str, Dict[str, Any]] = {}

        for snap in self.device_snapshots:
            for dev in snap.get("devices", []):
                mac = dev.get("mac")
                if not mac:
                    continue
                pkts = dev.get("frame_count", dev.get("packets", 0))
                rssi = dev.get("last_rssi_dbm", dev.get("rssi", -100))

                if mac not in device_map:
                    device_map[mac] = {
                        "mac": mac,
                        "is_ap": dev.get("is_ap", False),
                        "packets": pkts,
                        "rssi_samples": [rssi]
                    }
                else:
                    device_map[mac]["packets"] = max(device_map[mac]["packets"], pkts)
                    device_map[mac]["rssi_samples"].append(rssi)

        results = []
        ap_count = 0
        sta_count = 0

        for mac, d in device_map.items():
            if d["is_ap"]:
                ap_count += 1
            else:
                sta_count += 1

            rssi_list = d["rssi_samples"]
            results.append({
                "mac": mac,
                "role": "AP" if d["is_ap"] else "STA",
                "packets": d["packets"],
                "rssi_mean": round(statistics.mean(rssi_list), 1),
                "rssi_min": min(rssi_list),
                "rssi_max": max(rssi_list)
            })

        results.sort(key=lambda x: x["packets"], reverse=True)

        return {
            "unique_devices": len(results),
            "ap_count": ap_count,
            "sta_count": sta_count,
            "top_devices": results[:10],
            "all_devices": results
        }

    def audit_evidence_chain(self) -> Dict[str, Any]:
        if not self.evidence_blocks:
            return {"status": "NO_BLOCKS", "is_valid": True, "count": 0}

        sorted_blocks = sorted(self.evidence_blocks, key=lambda x: x.get("index", 0))
        for i, b in enumerate(sorted_blocks):
            idx = b.get("index", 0)
            ts = b.get("timestamp_ms", 0)
            etype = b.get("event_type", "")
            sev = b.get("severity", "")
            desc = b.get("description", "")
            prev_h = b.get("prev_hash", "")
            block_h = b.get("block_hash", "")

            if idx == 0:
                if prev_h != GENESIS_PREV_HASH:
                    return {"status": "TAMPERED", "is_valid": False, "failed_index": 0, "reason": "Invalid Genesis prev_hash"}
            elif i > 0:
                prev_b = sorted_blocks[i - 1]
                if prev_h != prev_b.get("block_hash"):
                    return {"status": "BROKEN_LINK", "is_valid": False, "failed_index": idx, "reason": "Previous hash link broken"}

            canonical = build_canonical(idx, ts, etype, sev, desc, prev_h)
            calc_hash = compute_sha256(canonical)
            if calc_hash != block_h:
                return {"status": "TAMPERED", "is_valid": False, "failed_index": idx, "reason": "SHA-256 digest mismatch"}

        return {
            "status": "VALID",
            "is_valid": True,
            "count": len(sorted_blocks),
            "genesis_hash": sorted_blocks[0].get("block_hash"),
            "tip_hash": sorted_blocks[-1].get("block_hash")
        }

    def generate_report(self) -> Dict[str, Any]:
        tp = self.analyze_throughput()
        dev = self.analyze_devices()
        audit = self.audit_evidence_chain()

        report = {
            "session_id": self.meta.get("session_id", os.path.basename(self.session_dir)),
            "session_dir": self.session_dir,
            "start_time": self.meta.get("start_iso", "N/A"),
            "duration_sec": self.meta.get("duration_sec", 0),
            "throughput_metrics": tp,
            "device_metrics": dev,
            "cryptographic_audit": audit
        }
        return report

    def print_summary(self, report: Dict[str, Any]):
        tp = report["throughput_metrics"]
        dev = report["device_metrics"]
        audit = report["cryptographic_audit"]

        print("=" * 76)
        print("          FORENSITAP-ESP32 POST-CAPTURE FORENSIC ANALYSIS")
        print("=" * 76)
        print(f"Session Identifier : {report['session_id']}")
        print(f"Directory          : {report['session_dir']}")
        print(f"Total Duration     : {report['duration_sec']}s ({tp.get('samples', 0)} telemetry records)")
        print("-" * 76)

        print("[+] WIRELESS TRAFFIC PROFILE")
        if tp.get("samples", 0) > 0:
            print(f"  * Observed Frame Rate : Mean: {tp['fps_mean']:.1f} fps | Median: {tp['fps_median']:.1f} fps")
            print(f"  * Peak Activity Rate  : {tp['fps_max']:.1f} fps (Min: {tp['fps_min']:.1f} fps)")
            print(f"  * Throughput Bandwidth: Mean: {tp['byte_rate_mean_kbs']:.1f} KB/s | Peak: {tp['byte_rate_peak_kbs']:.1f} KB/s")
            print(f"  * Frame Composition   : {tp['total_observed_frames']} total ({tp['management_frames']} mgmt, {tp['data_frames']} data)")
            print(f"  * Buffer Reliability  : {tp['dropped_frames']} dropped frames")
        else:
            print("  * No throughput records captured in this session.")

        print("-" * 76)
        print("[+] 802.11 DEVICE ACTIVITY & FLOW DISTRIBUTION")
        print(f"  * Tracked Entities    : {dev.get('unique_devices', 0)} total ({dev.get('ap_count', 0)} APs, {dev.get('sta_count', 0)} Stations)")
        print("  * Top Transmitting Nodes:")
        for i, d in enumerate(dev.get("top_devices", [])[:5], start=1):
            print(f"     {i}. [{d['mac']}] ({d['role']}) - {d['packets']} pkts | Avg RSSI: {d['rssi_mean']} dBm")

        print("-" * 76)
        print("[+] CRYPTOGRAPHIC EVIDENCE CHAIN AUDIT")
        if audit["is_valid"]:
            print(f"  * Status              : [+] VERIFIED INTACT ({audit.get('count', 0)} blocks inspected)")
            if audit.get("genesis_hash"):
                print(f"  * Genesis Block Hash  : {audit['genesis_hash']}")
                print(f"  * Chain Tip Hash      : {audit['tip_hash']}")
        else:
            print(f"  * Status              : [-] COMPROMISED / TAMPER DETECTED!")
            print(f"  * Failed Block Index  : #{audit.get('failed_index')}")
            print(f"  * Failure Diagnosis   : {audit.get('reason')}")

        print("=" * 76)

def find_latest_session(base_dir: str) -> Optional[str]:
    sessions = glob.glob(os.path.join(base_dir, "session_*"))
    if not sessions:
        return None
    sessions.sort(key=os.path.getmtime)
    return sessions[-1]

def main():
    parser = argparse.ArgumentParser(description="ForensiTap Offline Forensic Analyzer")
    parser.add_argument("--session-dir", help="Path to specific session directory")
    parser.add_argument("--latest", action="store_true", help="Analyze most recent session in datasets/sessions")
    parser.add_argument("--export-json", action="store_true", help="Write analysis_summary.json into session dir")
    args = parser.parse_args()

    default_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datasets", "sessions")

    target_dir = args.session_dir
    if not target_dir and args.latest:
        target_dir = find_latest_session(default_base)
        if not target_dir:
            print("[-] No existing sessions found in datasets/sessions.")
            sys.exit(1)

    if not target_dir:
        # Check if any sessions exist
        target_dir = find_latest_session(default_base)
        if not target_dir:
            print("[-] Please provide --session-dir <path> or run collector.py first.")
            sys.exit(1)

    analyzer = ForensicTrafficAnalyzer(target_dir)
    if not analyzer.load_data():
        print(f"[-] Could not load forensic data from {target_dir}")
        sys.exit(1)

    report = analyzer.generate_report()
    analyzer.print_summary(report)

    if args.export_json or True:
        out_path = os.path.join(target_dir, "analysis_summary.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[*] Comprehensive forensic report exported to {out_path}")

if __name__ == "__main__":
    main()
