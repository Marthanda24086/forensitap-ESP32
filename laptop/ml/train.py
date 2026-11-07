#!/usr/bin/env python3
"""
ForensiTap-ESP32: Unsupervised Anomaly Detection Model Training
Stage 17 Implementation (Laptop-Side Machine Learning Extension)

Extracts 7-dimensional statistical feature vectors from captured session logs,
trains a robust ellipsoidal density anomaly detector with explainable feature
attribution, calibrates decision boundaries, and saves the trained model artifact.

Usage:
    python laptop/ml/train.py [--sessions-dir ../../datasets/sessions]
                              [--output-model models/forensitap_anomaly_model.json]
"""

import argparse
import glob
import json
import math
import os
import random
import statistics
import sys
from typing import Dict, List, Any, Tuple

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "forensitap_anomaly_model.json")
DEFAULT_SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datasets", "sessions")

FEATURE_NAMES = [
    "frame_rate",
    "byte_rate",
    "average_frame_size",
    "unique_peers",
    "management_frame_ratio",
    "traffic_burst_score",
    "frame_rate_zscore"
]

MIN_MADS = {
    "frame_rate": 2.0,
    "byte_rate": 500.0,
    "average_frame_size": 10.0,
    "unique_peers": 2.0,
    "management_frame_ratio": 0.02,
    "traffic_burst_score": 0.2,
    "frame_rate_zscore": 0.3
}

class RobustAnomalyDetector:
    def __init__(self, contamination: float = 0.02):
        self.contamination = contamination
        self.medians: Dict[str, float] = {}
        self.mads: Dict[str, float] = {}
        self.weights: Dict[str, float] = {
            "frame_rate": 1.2,
            "byte_rate": 1.0,
            "average_frame_size": 0.8,
            "unique_peers": 1.0,
            "management_frame_ratio": 2.0,  # High sensitivity to deauth/beacon attacks
            "traffic_burst_score": 1.8,     # High sensitivity to micro-bursts
            "frame_rate_zscore": 1.5        # Sensitive to baseline shifts
        }
        self.threshold: float = 3.0
        self.is_trained: bool = False

    def _compute_mad(self, feature_name: str, values: List[float], median: float) -> float:
        devs = [abs(v - median) for v in values]
        raw_mad = statistics.median(devs) * 1.4826  # Normal-consistent MAD scale
        min_allowed = MIN_MADS.get(feature_name, 1.0)
        return max(raw_mad, min_allowed)

    def fit(self, samples: List[Dict[str, float]]):
        if len(samples) < 5:
            raise ValueError(f"Insufficient training samples ({len(samples)}). Minimum 5 required.")

        for name in FEATURE_NAMES:
            vals = [s.get(name, 0.0) for s in samples]
            med = statistics.median(vals)
            mad = self._compute_mad(name, vals, med)
            self.medians[name] = med
            self.mads[name] = mad

        # Compute training scores to calibrate threshold
        scores = [self.score_sample(s)["distance"] for s in samples]
        scores.sort()

        # Set threshold at (1 - contamination) quantile
        cut_idx = min(len(scores) - 1, int((1.0 - self.contamination) * len(scores)))
        self.threshold = max(2.5, scores[cut_idx])
        self.is_trained = True

    def score_sample(self, sample: Dict[str, float]) -> Dict[str, Any]:
        weighted_sq_sum = 0.0
        feature_attributions: Dict[str, float] = {}

        for name in FEATURE_NAMES:
            val = float(sample.get(name, 0.0))
            med = self.medians.get(name, 0.0)
            mad = self.mads.get(name, 1.0)
            w = self.weights.get(name, 1.0)

            # Robust Z-score
            z = (val - med) / mad
            weighted_z_sq = w * (z ** 2)
            weighted_sq_sum += weighted_z_sq

            feature_attributions[name] = round(z, 2)

        distance = math.sqrt(weighted_sq_sum)
        # Map distance to sigmoid probability [0.0 to 1.0]
        prob = 1.0 / (1.0 + math.exp(-1.2 * (distance - self.threshold)))
        is_anomaly = distance >= self.threshold

        return {
            "distance": round(distance, 3),
            "anomaly_probability": round(prob, 4),
            "is_anomaly": is_anomaly,
            "threshold": round(self.threshold, 3),
            "attributions": feature_attributions
        }

    def save(self, filepath: str):
        data = {
            "model_type": "ForensiTapRobustEllipsoidalDetector",
            "version": "1.0.0",
            "feature_names": FEATURE_NAMES,
            "medians": self.medians,
            "mads": self.mads,
            "weights": self.weights,
            "threshold": self.threshold,
            "contamination": self.contamination
        }
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "RobustAnomalyDetector":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        detector = cls(contamination=data.get("contamination", 0.02))
        detector.medians = data["medians"]
        detector.mads = data["mads"]
        detector.weights = data["weights"]
        detector.threshold = data["threshold"]
        detector.is_trained = True
        return detector


def extract_features_from_sessions(sessions_dir: str) -> List[Dict[str, float]]:
    samples = []
    session_dirs = glob.glob(os.path.join(sessions_dir, "session_*"))

    for sdir in session_dirs:
        telem_file = os.path.join(sdir, "telemetry.jsonl")
        if not os.path.exists(telem_file):
            continue
        with open(telem_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                feat = entry.get("features", {})
                b = feat.get("baseline", {})
                if not feat:
                    continue

                sample = {
                    "frame_rate": float(feat.get("frame_rate", 0.0)),
                    "byte_rate": float(feat.get("byte_rate", 0.0)),
                    "average_frame_size": float(feat.get("average_frame_size", 0.0)),
                    "unique_peers": float(feat.get("unique_peers", 0.0)),
                    "management_frame_ratio": float(feat.get("management_frame_ratio", 0.0)),
                    "traffic_burst_score": float(feat.get("traffic_burst_score", 1.0)),
                    "frame_rate_zscore": float(b.get("frame_rate_zscore", 0.0))
                }
                samples.append(sample)

    return samples

def generate_synthetic_baseline() -> List[Dict[str, float]]:
    """Generates nominal benign 802.11 baseline samples if no session logs are present."""
    random.seed(42)
    samples = []
    for _ in range(80):
        fps = random.gauss(100.0, 15.0)
        byte_rate = fps * random.gauss(210.0, 20.0)
        avg_size = byte_rate / fps if fps > 0 else 200.0
        peers = int(random.gauss(16, 2))
        mgmt_ratio = max(0.05, min(0.35, random.gauss(0.18, 0.04)))
        burst = max(1.0, random.gauss(1.8, 0.4))
        z = (fps - 100.0) / 15.0

        samples.append({
            "frame_rate": round(fps, 1),
            "byte_rate": round(byte_rate, 1),
            "average_frame_size": round(avg_size, 1),
            "unique_peers": peers,
            "management_frame_ratio": round(mgmt_ratio, 3),
            "traffic_burst_score": round(burst, 2),
            "frame_rate_zscore": round(z, 2)
        })
    return samples

def evaluate_on_attacks(model: RobustAnomalyDetector):
    attacks = [
        {
            "name": "Deauthentication Flood Attack",
            "sample": {
                "frame_rate": 350.0, "byte_rate": 18000.0, "average_frame_size": 52.0,
                "unique_peers": 4, "management_frame_ratio": 0.88,  # Extreme mgmt ratio
                "traffic_burst_score": 4.5, "frame_rate_zscore": 4.2
            }
        },
        {
            "name": "High-Volume Traffic Spike (Exfiltration)",
            "sample": {
                "frame_rate": 580.0, "byte_rate": 320000.0, "average_frame_size": 550.0,
                "unique_peers": 22, "management_frame_ratio": 0.05,
                "traffic_burst_score": 5.8, "frame_rate_zscore": 6.8  # Extreme Z-score
            }
        },
        {
            "name": "Micro-Burst Pulse Jamming",
            "sample": {
                "frame_rate": 120.0, "byte_rate": 30000.0, "average_frame_size": 250.0,
                "unique_peers": 15, "management_frame_ratio": 0.22,
                "traffic_burst_score": 8.2, "frame_rate_zscore": 1.2  # Extreme burst
            }
        },
        {
            "name": "Benign Validation Sample",
            "sample": {
                "frame_rate": 95.0, "byte_rate": 19000.0, "average_frame_size": 200.0,
                "unique_peers": 16, "management_frame_ratio": 0.16,
                "traffic_burst_score": 1.6, "frame_rate_zscore": -0.3
            }
        }
    ]

    print("\n" + "=" * 76)
    print("           MODEL EVALUATION ON BENCHMARK ATTACK SCENARIOS")
    print("=" * 76)
    for at in attacks:
        res = model.score_sample(at["sample"])
        verdict = "ANOMALY (DETECTED)" if res["is_anomaly"] else "BENIGN (NOMINAL)"
        print(f"Scenario : {at['name']:<42} | Verdict: {verdict}")
        print(f"  * Distance: {res['distance']:<6} (Threshold: {res['threshold']}) | Prob: {res['anomaly_probability']*100:.1f}%")
        top_attrs = sorted(res["attributions"].items(), key=lambda x: abs(x[1]), reverse=True)[:2]
        attr_str = ", ".join([f"{k}: {v:+} Z" for k, v in top_attrs])
        print(f"  * Key Drivers: {attr_str}\n")
    print("=" * 76)

def main():
    parser = argparse.ArgumentParser(description="ForensiTap Anomaly Detector Model Training")
    parser.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR, help="Path to datasets/sessions")
    parser.add_argument("--output-model", default=DEFAULT_MODEL_PATH, help="Path to save trained model JSON")
    args = parser.parse_args()

    print("=" * 76)
    print("      FORENSITAP-ESP32 MACHINE LEARNING MODEL TRAINING PIPELINE")
    print("=" * 76)
    print(f"[*] Ingesting Sessions from: {args.sessions_dir}")

    samples = extract_features_from_sessions(args.sessions_dir)
    if len(samples) < 20:
        print(f"[*] Only {len(samples)} empirical samples found. Augmenting with synthetic nominal baseline to ensure statistical stability...")
        samples.extend(generate_synthetic_baseline())

    print(f"[*] Training on {len(samples)} benign feature vectors...")

    detector = RobustAnomalyDetector(contamination=0.03)
    detector.fit(samples)

    detector.save(args.output_model)
    print(f"[+] Model successfully trained and saved to: {args.output_model}")
    print(f"[*] Calibrated Anomaly Threshold : {detector.threshold:.3f}")

    evaluate_on_attacks(detector)

if __name__ == "__main__":
    main()
