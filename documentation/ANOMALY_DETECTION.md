# ForensiTap-ESP32: Rule-Based Anomaly Detection

## Overview

The **Anomaly Detection Engine** (`ForensiTapDetector`, module code `DET`) executes lightweight, deterministic, rule-based security evaluations directly on the ESP32 micro-controller. By analyzing streaming statistical metrics computed by the Feature Engine (`FENG`), hardware queue diagnostics from the Wi-Fi Monitor (`MON`), and metadata events from the device tracker, the engine identifies anomalous wireless events in real time without requiring heavy computational resources or neural network inferences.

---

## Detection Architecture

```mermaid
flowchart TD
    subgraph Data Sources
        FENG[Feature Engine<br/>Statistical Vectors]
        MON[Wi-Fi Monitor<br/>Hardware Queue Health]
        META[Metadata Tracker<br/>Device Discovery]
    end

    subgraph Detector Subsystem [ForensiTapDetector (DET)]
        R1[Rule 1: Traffic Spike Detection<br/>Z-Score >= 3.0]
        R2[Rule 2: Management Anomaly<br/>Mgmt Ratio >= 0.60]
        R3[Rule 3: New Device Discovered<br/>Tracked Table Ingestion]
        R4[Rule 4: Activity Burstiness<br/>Burst Score >= 5.0]
        R5[Rule 5: Monitor Queue Health<br/>Frame Drop Count Delta]
        
        COOL[Cooldown Filter<br/>30-second deduplication]
        RING[Circular FIFO Ring Buffer<br/>16 SecurityAlert Slots]
    end

    subgraph Egress & Integration
        API[REST API: GET /api/alerts]
        LOG[Diagnostic Logger & Serial]
        CHAIN[Stage 12 Hash Chain Target]
    end

    FENG --> R1 & R2 & R4
    META --> R3
    MON --> R5

    R1 & R2 & R4 & R5 --> COOL
    R3 --> RING
    COOL --> RING

    RING --> API
    RING --> LOG
    RING -.-> CHAIN
```

---

## Deterministic Rule Specifications

| Rule ID | Anomaly / Event Name | Trigger Condition | Severity | Default Cooldown | Security Significance |
|---|---|---|---|---|---|
| **Rule 1** | `TRAFFIC_SPIKE_DETECTED` | `rateDeviationZScore >= 3.0`<br/>AND `frameRateFps > 20.0`<br/>AND `baselineMeanFps > 5.0` | `WARNING` | 30 seconds | Detects abrupt traffic surges, high-volume data exfiltration, or active network probing. |
| **Rule 2** | `MGMT_FRAME_FLOOD` | `mgmtFrameRatio >= 0.60`<br/>AND `windowFrameCount >= 20` | `WARNING` | 30 seconds | Identifies deauthentication/disassociation floods, aggressive beacon stuffing, or rogue AP scanning. |
| **Rule 3** | `NEW_DEVICE_OBSERVED` | New unique MAC inserted into device table (`notifyNewDevice`) | `INFO` | None (Per-MAC) | Logs appearance of previously unseen stations or rogue access points. |
| **Rule 4** | `ACTIVITY_BURST` | `burstinessScore >= 5.0`<br/>AND `windowFrameCount >= 10` | `WARNING` | 30 seconds | Pinpoints intense short-duration transmission bursts (e.g., beacon spam, pulse jamming, or rapid bursts). |
| **Rule 5** | `BUFFER_OVERFLOW_RISK` | `droppedFramesCount > lastDropped` | `ERROR` | 30 seconds | Alerts when the FreeRTOS ingestion queue drops frames due to CPU saturation or heavy channel load. |

---

## Memory & Performance Design

1. **Zero Dynamic Allocation at Runtime:**
   - Static alert ring buffer with 16 fixed `SecurityAlert` slots (`MAX_STORED_ALERTS 16`).
   - Total memory footprint: `16 * 108 bytes ≈ 1.7 KB` in static RAM.
   - Fixed description buffer of 96 bytes eliminates heap fragmentation (`snprintf` with safe bounds).

2. **Deduplication & Cooldown Timers:**
   - Prevents log storms and serial flooding during persistent flood attacks (e.g. continuous deauth attacks).
   - Independent cooldown timestamps per rule category (`30000 ms` default).

3. **Sub-millisecond Evaluation:**
   - Evaluated periodically once per second (`1000 ms` interval) in the non-blocking main loop.
   - Fast scalar comparisons over pre-computed metrics from `FeatureVector`.

---

## REST API Interface

### Endpoint: `GET /api/alerts`

Returns the most recent security alerts held in the FIFO circular ring buffer.

**Response Structure (JSON):**
```json
{
  "total_alerts_generated": 3,
  "stored_alerts_count": 3,
  "max_alert_capacity": 16,
  "cooldown_seconds": 30,
  "thresholds": {
    "spike_z_score": 3.0,
    "mgmt_ratio_pct": 60.0,
    "burst_score": 5.0
  },
  "alerts": [
    {
      "id": 1,
      "timestamp_ms": 15420,
      "type": "NEW_DEVICE_OBSERVED",
      "severity": "INFO",
      "description": "New Station discovered: 42:CF:AA:4B:B3:45 (RSSI: -64 dBm)"
    },
    {
      "id": 2,
      "timestamp_ms": 45120,
      "type": "MGMT_FRAME_FLOOD",
      "severity": "WARNING",
      "description": "Excessive management frames: 72.4% (Threshold: 60.0%)"
    }
  ]
}
```

---

## Verification & Unit Testing

A comprehensive test suite is provided in `tests/test_detector.py` validating:
- Rule 1 traffic spike triggering and Z-score gating.
- 30-second cooldown suppression and post-cooldown re-triggering.
- Rule 2 management flood threshold evaluation.
- Rule 3 new device notification handling.
- Rule 4 activity burst detection.
- Rule 5 buffer overflow alert generation.
- Circular FIFO ring buffer eviction (preserving the 16 most recent alerts).

Execute tests via:
```bash
python tests/test_detector.py
```
