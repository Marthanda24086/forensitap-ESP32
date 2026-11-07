# ForensiTap-ESP32: Low-Cost Wireless Network Forensics and Tamper-Evident Monitoring Appliance

ForensiTap-ESP32 is an academic embedded security appliance designed to provide low-cost 802.11 wireless network monitoring, real-time edge anomaly detection, cryptographic evidence chain integrity, and physical tamper monitoring using an ESP32 microcontroller paired with host-side analytics.

---

## 1. Project Directory Structure

```text
ForensiTap-ESP32/
│
├── firmware/
│   ├── main/                 # Top-level firmware sketches and execution entry points
│   │   ├── ForensiTap.ino    # Modular main application entry point (Stage 5-10)
│   │   ├── system_config.h   # Central system configuration & version metadata
│   │   ├── events.h          # Standardized event schema & severity taxonomy
│   │   ├── module_interface.h# Abstract lifecycle contract for subsystems
│   │   ├── diagnostic_logger.h/cpp # Structured logging facility
│   │   ├── network_manager.h/cpp   # Wi-Fi station connectivity manager
│   │   ├── wifi_credentials.h# Wi-Fi SSID & password configuration
│   │   ├── wifi_monitor.h/cpp# 802.11 sniffer, metadata processor & device table
│   │   ├── feature_engine.h/cpp # 10s sliding-window statistical feature engine
│   │   ├── detector.h/cpp    # Rule-based deterministic anomaly detection engine (Stage 11)
│   │   ├── evidence_logger.h/cpp # SHA-256 tamper-evident cryptographic hash chain (Stage 12)
│   │   ├── api_server.h/cpp  # REST HTTP API server
│   │   └── ForensiTap_Stage4/ # Preserved Stage 4 hardware verification sketch
│   ├── feature_engine/       # Edge statistical windowing and feature extraction
│   ├── wifi_monitor/         # 802.11 promiscuous frame capture & device tracker
│   ├── api_server/           # Local REST HTTP API server module
│   ├── detector/             # On-device anomaly detection and rule/heuristic evaluation (Stage 11)
│   ├── evidence_logger/      # Tamper-evident log storage with cryptographic hash chains (Stage 12)
│   ├── tamper_sensor/        # Enclosure security, Hall-effect magnetic sensor ISR
│   └── storage/              # Non-volatile storage management (LittleFS)
│
├── dashboard/                # Front-end dashboard for visualization and live telemetry feeds (Stage 13)
│
├── laptop/
│   ├── collector/            # Python streaming data collector (Stage 14)
│   ├── ml/                   # Machine learning model training & inference (Postponed: Stage 17)
│   ├── analytics/            # Offline forensic traffic inspection, flow statistics, and metrics (Stage 14)
│   └── verification/         # Independent evidence audit scripts verifying hash chains (Stage 12/14)
│
├── datasets/                 # Reference PCAP files, benign baselines, and synthetic attack vectors
│
├── tests/                    # Firmware unit tests, simulated traffic tests, and HIL scripts
│   ├── test_metadata_processing.py # Unit tests for MAC sanitization and LRU eviction
│   ├── test_feature_engine.py      # Unit tests for sliding window stats & Welford baseline
│   ├── test_detector.py            # Unit tests for anomaly rules, thresholds, and ring buffer
│   ├── test_evidence_logger.py     # Unit tests for SHA-256 hash chain and tamper detection
│   ├── test_dashboard.py           # Unit tests for web dashboard DOM & API bindings
│   ├── test_analytics.py           # Unit tests for forensic collector & analytics pipeline
│   ├── stress_test.py              # Full multi-threaded system integration and stress test harness
│   └── test_ml.py                  # Unit tests for unsupervised anomaly detection ML model
│
├── documentation/            # Technical specifications, phase verification reports, and architecture guides
│   ├── HOW_IT_WORKS_AND_WHAT_IT_SOLVES.md # Master Guide: Problem solved, operational layers, and attack catalog
│   ├── COMPLETE_SYSTEM_ARCHITECTURE.md    # Master Architecture: Silicon model, coexistence, memory, and DAG
│   ├── ARCHITECTURE.md       # Core system architecture specification
│   ├── STAGE_4_HARDWARE_TEST.md # Initial hardware verification & driver setup guide
│   ├── WIFI_NETWORKING.md    # Stage 6 Wi-Fi setup & radio coexistence analysis
│   ├── API_REFERENCE.md      # Stage 7 REST HTTP API documentation & test commands
│   ├── WIFI_MONITORING.md    # Stage 8 Promiscuous mode architecture & frame capture
│   ├── METADATA_PROCESSING.md# Stage 9 Metadata extraction & LRU device tracking
│   ├── FEATURE_ENGINE.md     # Stage 10 Statistical sliding window & baseline metrics
│   ├── ANOMALY_DETECTION.md  # Stage 11 Rule-based anomaly detection & alert buffer
│   ├── FORENSIC_LOGGING.md   # Stage 12 Cryptographic hash chain & audit verification
│   ├── DASHBOARD.md          # Stage 13 Front-end web dashboard guide & architecture
│   ├── DATA_COLLECTION_AND_ANALYTICS.md # Stage 14 Collector & offline forensic analytics
│   ├── STRESS_TESTING.md     # Stage 15 Full system stress & integration test report
│   ├── VALIDATION_REPORT.md  # Stage 16 Comprehensive empirical evaluation & benchmarks
│   ├── LIMITATIONS.md        # Stage 16 Hardware, protocol, and architectural limitations
│   ├── USER_GUIDE.md         # Stage 16 Complete operator, installation, and usage manual
│   └── MACHINE_LEARNING.md   # Stage 17 Host-side ML model training & streaming inference
│
└── README.md                 # Project overview, development guide, and system roadmap
```

---

## 2. Current Implementation Status

- **Project Status:** **Complete System Implementation & Hardware Validation (Stages 1–17 Fully Completed & Verified)**
- **Completed Stages:**
  - Stage 1–2: Project conception, requirements specification, and architecture definition.
  - Stage 3: Modular project directory structure establishment.
  - Stage 4: Initial hardware boot test, silicon diagnostics, and 115200 baud serial verification.
  - Stage 5: Modular application core (`ForensiTap.ino`), lifecycle interface (`IModule`), standardized event taxonomy (`events.h`), structured diagnostic logger (`DiagnosticLogger`), and architecture document (`ARCHITECTURE.md`).
  - Stage 6: Wi-Fi station connectivity manager (`ForensiTapNetworkManager`), event-driven DHCP lease negotiation, non-blocking auto-reconnect, and single-radio coexistence documentation.
  - Stage 7: REST HTTP API server (`ForensiTapApiServer`) on port 80 with CORS support, JSON health, statistics, device observations, features, forensic log endpoints, and CSV/JSON export.
  - Stage 8: 802.11 promiscuous frame capture engine (`ForensiTapWifiMonitor`) with hardware packet filtering, sub-microsecond `IRAM_ATTR` RX callback, bounded FreeRTOS queue, live frame rate counters, and real-time integration with `GET /api/stats`.
  - Stage 9: Frame metadata processing pipeline, MAC address sanitization (filtering broadcast/multicast), bounded 32-entry device tracking table with deterministic LRU eviction, malformed frame detection, and chunked streaming endpoint `GET /api/devices`.
  - Stage 10: 10-second sliding-window statistical feature engine (`ForensiTapFeatureEngine`) computing frame rate, byte rate, average frame size, unique peers, management frame ratio, and traffic burst score. Adaptive baseline tracking using Welford's algorithm (mean, standard deviation, and Z-score deviation), integrated into `GET /api/features`.
  - Stage 11: Rule-based anomaly detection engine (`ForensiTapDetector`) evaluating 5 deterministic security rules (traffic spike Z-score, management frame flooding, new device discovery, burstiness scores, and queue health), 30s alert cooldown deduplication, 16-slot FIFO ring buffer, and REST endpoint `GET /api/alerts`.
  - Stage 12: Cryptographic SHA-256 forensic evidence logging subsystem (`ForensiTapEvidenceLogger`) implementing append-only hash chains with Genesis block initialization, automatic sealing of detector alerts, on-chip hash verification (`GET /api/logs/verify`), chunked streaming log endpoint (`GET /api/logs`), and laptop independent audit CLI (`laptop/verification/verify_logs.py`).
  - Stage 13: Front-end cybersecurity web dashboard (`dashboard/index.html`, `style.css`, `app.js`) featuring real-time Chart.js frame rate telemetry, LRU device tracking table, feature vector monitor, live security alerts feed, one-click on-chip hash chain audit, and CSV evidence export.
  - Stage 14: Streaming forensic collector (`laptop/collector/collector.py`) and offline traffic analytics engine (`laptop/analytics/traffic_analysis.py`) with append-only JSONL multi-stream storage, MAC flow statistics, RSSI distribution, throughput percentiles, and automatic SHA-256 cryptographic chain auditing.
  - Stage 15: Full system integration & multi-threaded stress test harness (`tests/stress_test.py`) validating concurrent API throughput (11.9 req/s), 100% request success rate, heap stability (zero leak), and intact cryptographic evidence chain during continuous 802.11 sniffing.
  - Stage 16: Comprehensive empirical test report (`VALIDATION_REPORT.md`), academic engineering constraints analysis (`LIMITATIONS.md`), and end-to-end operator manual (`USER_GUIDE.md`).
  - Stage 17: Host-side machine learning anomaly detection extension (`laptop/ml/train.py`, `inference.py`) implementing an unsupervised robust ellipsoidal detector over 7-dimensional feature spaces with explainable feature attribution.

---

## 3. Implementation Roadmap

```text
[Stage 1-2] Conception & Architecture Definition           (COMPLETED)
[Stage 3]   Modular Project Structure Creation             (COMPLETED)
[Stage 4]   Initial Hardware Firmware & Serial Test        (COMPLETED)
[Stage 5]   Firmware Architecture & Cleanup                (COMPLETED)
[Stage 6]   Wi-Fi Connection & Network Management          (COMPLETED)
[Stage 7]   Lightweight HTTP Server & REST API             (COMPLETED)
[Stage 8]   802.11 Promiscuous Sniffer & Ingestion         (COMPLETED)
[Stage 9]   Frame Metadata Processing Pipeline             (COMPLETED)
[Stage 10]  Statistical Feature Extraction Engine          (COMPLETED)
[Stage 11]  Rule-Based Anomaly Detection Engine            (COMPLETED)
[Stage 12]  SHA-256 Tamper-Evident Evidence Logger         (COMPLETED)
[Stage 13]  Web Dashboard Interface                        (COMPLETED)
[Stage 14]  Laptop Data Collection & Audit Utilities       (COMPLETED)
[Stage 15]  Full System Integration & Stress Testing       (COMPLETED)
[Stage 16]  Comprehensive Validation & Technical Reports   (COMPLETED)
[Stage 17]  Host-Side Machine Learning Extension           (COMPLETED)
```
