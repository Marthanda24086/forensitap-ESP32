# ForensiTap-ESP32: Data Collection & Forensic Analytics Pipeline

## 1. Overview

The **Laptop Data Collection & Forensic Analytics Pipeline** (Stage 14) bridges the resource-constrained ESP32 sensor appliance with high-performance host-side storage and offline digital forensic inspection. 

The pipeline consists of two primary subsystems:
1. **Streaming Data Collector (`laptop/collector/collector.py`):** Asynchronously polls the ESP32 REST API, ingests streaming telemetry, device tables, and cryptographic evidence blocks, writes append-only JSONL files, and handles transient wireless link failures with exponential backoff.
2. **Offline Traffic Analytics Engine (`laptop/analytics/traffic_analysis.py`):** Ingests recorded sessions, computes statistical metrics, analyzes device flow distributions, characterizes burstiness, and cryptographically audits evidence chains from Genesis to tip.

---

## 2. Pipeline Architecture

```mermaid
flowchart TD
    subgraph Edge Appliance [ESP32 ForensiTap (192.168.1.26)]
        API[ForensiTapApiServer]
        T_EP[/api/health & /api/stats & /api/features]
        D_EP[/api/devices]
        L_EP[/api/logs]
    end

    subgraph Host Collector [laptop/collector/collector.py]
        INGEST[HTTP Streaming Ingestion Engine]
        BACKOFF[Fault-Tolerant Exponential Backoff]
        DEDUP[Index Deduplicator]
    end

    subgraph Structured Storage [datasets/sessions/session_YYYYMMDD_HHMMSS/]
        META[session_meta.json]
        TELEM[telemetry.jsonl]
        DEVS[devices.jsonl]
        EVID[evidence_chain.jsonl]
    end

    subgraph Forensic Analytics [laptop/analytics/traffic_analysis.py]
        TP_ANALYSIS[Throughput & Volumetrics Engine]
        DEV_ANALYSIS[MAC Device Flow & RSSI Profiler]
        HASH_AUDIT[SHA-256 Mathematical Audit Engine]
        REP[analysis_summary.json & ASCII Report]
    end

    API --> INGEST
    INGEST --> BACKOFF --> INGEST
    INGEST --> DEDUP
    DEDUP --> TELEM & DEVS & EVID
    INGEST --> META

    TELEM & DEVS & EVID & META --> TP_ANALYSIS & DEV_ANALYSIS & HASH_AUDIT
    TP_ANALYSIS & DEV_ANALYSIS & HASH_AUDIT --> REP
```

---

## 3. Streaming Collector (`collector.py`)

### Features
- **Zero-Dependency Architecture:** Pure standard Python (`urllib.request`, `json`, `time`, `signal`).
- **Append-Only Fault-Tolerant Serialization:** Uses JSON Lines (`.jsonl`) so partial captures remain completely valid even if disrupted.
- **Deduplicated Evidence Chaining:** Tracks ingested block sequence indices (`set[int]`), ensuring newly sealed blocks from the ESP32's circular buffer are archived exactly once.
- **Graceful Signal Handling:** Intercepts `SIGINT` (Ctrl+C) and `SIGTERM`, writing closing metadata timestamps and summarizing the session.

### Execution
```bash
# Continuous collection with 2-second polling
python laptop/collector/collector.py

# Specify custom interval and duration (e.g. 60-second capture)
python laptop/collector/collector.py --interval 1.0 --duration 60

# Custom ESP32 target IP
python laptop/collector/collector.py --esp-url http://192.168.1.26
```

---

## 4. Forensic Traffic Analytics Engine (`traffic_analysis.py`)

### Features
- **Temporal & Throughput Analytics:** Computes minimum, maximum, mean, median, standard deviation, and 95th-percentile frame rates, bandwidth throughput in KB/s, management vs. data frame distribution, and hardware queue drop counts.
- **Device Flow & Signal Strength Profiling:** Aggregates unique MAC addresses, identifies Access Points vs. Client Stations, ranks top talkers by packet count, and computes per-device RSSI statistics (mean, min, max).
- **Independent Cryptographic Audit:** Recalculates every SHA-256 digest from the genesis block (`000...000` previous hash) up to the chain tip, detecting any post-capture file modification, line deletion, or bit corruption.
- **Structured JSON Export:** Automatically creates `analysis_summary.json` inside the session folder for archival or automated plotting.

### Execution
```bash
# Analyze the most recently captured session
python laptop/analytics/traffic_analysis.py --latest

# Analyze a specific session folder
python laptop/analytics/traffic_analysis.py --session-dir datasets/sessions/session_20261107_221715
```

---

## 5. Storage Schema Reference

Each capture run creates an isolated directory in `datasets/sessions/session_<TIMESTAMP>/`:

| File | Format | Contents |
|---|---|---|
| `session_meta.json` | JSON | Session ID, start/end timestamps, elapsed seconds, total cycles, total blocks, appliance target URL. |
| `telemetry.jsonl` | JSONL | Timestamped snapshots of system health, frame rates, byte rates, sliding-window features, and baseline Z-scores. |
| `devices.jsonl` | JSONL | Periodic snapshots of tracked MAC addresses, roles (AP/STA), frame counts, and RSSI readings. |
| `evidence_chain.jsonl` | JSONL | Append-only archive of cryptographically sealed SHA-256 blocks minted by the ESP32. |
| `analysis_summary.json` | JSON | Post-capture analytical metrics, device rankings, and cryptographic audit proofs. |
