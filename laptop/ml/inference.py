#!/usr/bin/env python3
"""
ForensiTap-ESP32: Real-Time Machine Learning Anomaly Inference
Stage 17 Implementation (Laptop-Side Machine Learning Extension)

Loads the trained anomaly detector model and scores:
1. Live streaming feature vectors directly from the running ESP32 appliance.
2. Historical sessions recorded by ForensiTapCollector.

Usage:
    python laptop/ml/inference.py --live [--esp-url http://192.168.1.26] [--interval 2.0]
    python laptop/ml/inference.py --latest
    python laptop/ml/inference.py --session-dir ../../datasets/sessions/session_...
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, Any, Optional

# Add parent directory to path to import train module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import RobustAnomalyDetector, DEFAULT_MODEL_PATH, DEFAULT_SESSIONS_DIR

DEFAULT_ESP_URL = "http://192.168.1.26"

def fetch_esp_features(base_url: str) -> Optional[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/features"
    req = urllib.request.Request(url, headers={"User-Agent": "ForensiTapMLInference/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None

def extract_vector(feat: Dict[str, Any]) -> Dict[str, float]:
    b = feat.get("baseline", {})
    return {
        "frame_rate": float(feat.get("frame_rate", 0.0)),
        "byte_rate": float(feat.get("byte_rate", 0.0)),
        "average_frame_size": float(feat.get("average_frame_size", 0.0)),
        "unique_peers": float(feat.get("unique_peers", 0.0)),
        "management_frame_ratio": float(feat.get("management_frame_ratio", 0.0)),
        "traffic_burst_score": float(feat.get("traffic_burst_score", 1.0)),
        "frame_rate_zscore": float(b.get("frame_rate_zscore", 0.0))
    }

def run_live_inference(model: RobustAnomalyDetector, esp_url: str, interval: float = 2.0):
    print("=" * 76)
    print("      FORENSITAP-ESP32 REAL-TIME ML ANOMALY INFERENCE STREAM")
    print("=" * 76)
    print(f"[*] Target Appliance : {esp_url}")
    print(f"[*] Model Threshold  : {model.threshold:.3f}")
    print(f"[*] Evaluation Rate  : Every {interval}s")
    print("=" * 76)
    print(f"{'Timestamp':<10} | {'Status':<9} | {'Dist':<7} | {'Prob':<6} | {'FPS':<6} | {'Key Feature Attribution'}")
    print("-" * 76)

    try:
        while True:
            t0 = time.time()
            data = fetch_esp_features(esp_url)
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            if not data:
                print(f"[{now_str}] [-] Appliance unreachable. Retrying...")
            else:
                sample = extract_vector(data)
                res = model.score_sample(sample)

                status_badge = "[ANOMALY]" if res["is_anomaly"] else "[BENIGN] "
                fps_val = f"{sample['frame_rate']:.1f}"
                prob_str = f"{res['anomaly_probability']*100:.0f}%"

                # Top driver
                top_attr = sorted(res["attributions"].items(), key=lambda x: abs(x[1]), reverse=True)[0]
                driver_str = f"{top_attr[0]}: {top_attr[1]:+} Z"

                print(f"{now_str:<10} | {status_badge} | {res['distance']:<7.2f} | {prob_str:<6} | {fps_val:<6} | {driver_str}")

            elapsed = time.time() - t0
            time.sleep(max(0.1, interval - elapsed))
    except KeyboardInterrupt:
        print("\n[*] Inference streaming terminated by user.")

def run_session_inference(model: RobustAnomalyDetector, session_dir: str):
    telem_path = os.path.join(session_dir, "telemetry.jsonl")
    if not os.path.exists(telem_path):
        print(f"[-] telemetry.jsonl not found in {session_dir}")
        return

    print("=" * 76)
    print("      FORENSITAP-ESP32 OFFLINE ML SESSION ANOMALY AUDIT")
    print("=" * 76)
    print(f"[*] Target Session   : {session_dir}")
    print(f"[*] Model Threshold  : {model.threshold:.3f}")
    print("=" * 76)

    total_records = 0
    anomalies_detected = 0

    with open(telem_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total_records += 1
            entry = json.loads(line)
            sample = extract_vector(entry.get("features", {}))
            res = model.score_sample(sample)

            if res["is_anomaly"]:
                anomalies_detected += 1
                dt = entry.get("datetime", "")[:19]
                top_driver = sorted(res["attributions"].items(), key=lambda x: abs(x[1]), reverse=True)[0]
                print(f"[!] {dt} | ANOMALY DETECTED | Dist: {res['distance']:.2f} | Prob: {res['anomaly_probability']*100:.1f}% | Driver: {top_driver[0]} ({top_driver[1]:+} Z)")

    print("-" * 76)
    print(f"Total Cycles Evaluated : {total_records}")
    print(f"Anomalies Flagged      : {anomalies_detected} ({(anomalies_detected/total_records*100.0) if total_records > 0 else 0:.1f}%)")
    status = "COMPROMISED / UNUSUAL BEHAVIOR OBSERVED" if anomalies_detected > 0 else "ALL TRAFFIC NOMINAL"
    print(f"Session Verdict        : {status}")
    print("=" * 76)

def main():
    parser = argparse.ArgumentParser(description="ForensiTap ML Anomaly Inference Engine")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="Path to trained model JSON")
    parser.add_argument("--live", action="store_true", help="Score streaming live ESP32 features")
    parser.add_argument("--esp-url", default=DEFAULT_ESP_URL, help="ESP32 API Base URL")
    parser.add_argument("--interval", type=float, default=2.0, help="Live scoring interval")
    parser.add_argument("--session-dir", help="Path to specific session directory to audit")
    parser.add_argument("--latest", action="store_true", help="Score most recent captured session")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"[-] Trained model not found at {args.model}. Please run laptop/ml/train.py first.")
        sys.exit(1)

    model = RobustAnomalyDetector.load(args.model)

    if args.live:
        run_live_inference(model, args.esp_url, args.interval)
        return

    target_dir = args.session_dir
    if args.latest or not target_dir:
        sessions = [os.path.join(DEFAULT_SESSIONS_DIR, s) for s in os.listdir(DEFAULT_SESSIONS_DIR) if s.startswith("session_")] if os.path.exists(DEFAULT_SESSIONS_DIR) else []
        if sessions:
            sessions.sort(key=os.path.getmtime)
            target_dir = sessions[-1]
        else:
            print("[-] No session directory found. Run collector.py or specify --session-dir <path>")
            sys.exit(1)

    run_session_inference(model, target_dir)

if __name__ == "__main__":
    main()
