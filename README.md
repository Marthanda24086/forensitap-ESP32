# ForensiTap-ESP32: Low-Cost Wireless Network Forensics & Tamper-Evident Security Appliance

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Hardware: ESP32](https://img.shields.io/badge/Hardware-ESP32--WROOM--32-red.svg)](https://www.espressif.com/)
[![Tests: 33 Passed](https://img.shields.io/badge/Tests-33%20Passed%20(100%25)-brightgreen.svg)](tests/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-cyan.svg)](https://marthanda24086.github.io/forensitap-ESP32/)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](laptop/)
[![Power: <0.8W](https://img.shields.io/badge/Power-<0.8W-green.svg)](documentation/HOW_IT_WORKS_AND_WHAT_IT_SOLVES.md)

ForensiTap-ESP32 is a low-cost, dedicated hardware security appliance built on an **ESP32 microcontroller** paired with host-side analytics and machine learning. It performs continuous, non-intrusive 802.11 Layer 2 promiscuous frame capture, extracts real-time statistical feature vectors, detects cyber attacks on the edge, and seals every security alert inside an immutable **SHA-256 cryptographic evidence hash chain**.

---

### 🌐 Next-Gen Digital Product & Interactive Web Console

> **Live Interactive Experience:** [https://marthanda24086.github.io/forensitap-ESP32/](https://marthanda24086.github.io/forensitap-ESP32/)  
> Features 5 dedicated views: **SOC Cockpit**, **2.4 GHz Airspace Radar** (interactive canvas with device HUD hover inspection), **SHA-256 Blockchain Explorer** (with interactive 1-byte tamper simulation), **Architecture Pipeline**, and **Docs & Specifications**. Supports **WebSerial API** for direct in-browser USB hardware connection.

---

## Multi-Tier System Topology

```text
                  PUBLIC INTERNET
                         │
                         ▼
              GitHub Pages Website
    (https://marthanda24086.github.io/forensitap-ESP32/)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
       Overview     Architecture   Demo Dashboard
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
                 GitHub Repository
                         │
                         ▼
                  Source Code
                         │
                         ▼
                   ESP32 Device (Hardware Appliance)
                         │
                         ▼
             Local Live Hardware Dashboard
                (http://192.168.1.26:8080)
```

---

## Why ForensiTap? (The Problems It Solves)

| Challenge | Traditional Approach | ForensiTap-ESP32 Approach |
| :--- | :--- | :--- |
| **Hardware Cost** | Enterprise WIDS sensors cost **$2,000–$5,000** per sensor plus recurring licenses. | Off-the-shelf **sub-$10 hardware** (ESP32-WROOM-32) running custom C++ firmware. |
| **Layer 2 Visibility** | Host firewalls, EDRs, and network gateways only see IP packets; raw 802.11 management frames are discarded by OS Wi-Fi drivers. | Dedicated 802.11 PHY promiscuous sniffer capturing beacons, probe requests, deauths, and associations. |
| **Evidence Tampering** | Syslog files and local text logs can easily be deleted, edited, or truncated by attackers who gain root access. | Immutable **SHA-256 cryptographic blockchain** where each alert links mathematically to its predecessor. |
| **Power & Portability** | Bulky x86 rack servers or laptops requiring 45W–300W power. | Low-power (<0.8W), fanless micro-appliance operable for days from an ordinary USB power bank. |
| **User Privacy** | Full packet capture (PCAP) stores unencrypted payloads, risking GDPR, HIPAA, and wiretap law violations. | **Zero payload retention**: extracts only 32-byte anonymized frame metadata (MAC, RSSI, frame type). |

---

## Detected Cyber Attacks & Threat Catalog

1. **802.11 Deauthentication / Disassociation Flooding (`MGMT_ANOMALY`)**:
   - Flags rapid bursts of deauth/disassoc frames designed to disconnect endpoints and force WPA2/WPA3 4-way handshakes for offline cracking.
2. **Statistical Traffic Rate Spikes (`TRAFFIC_SPIKE`)**:
   - Uses an online **Welford running baseline** to compute real-time Z-scores, raising alarms whenever packet arrival rates exceed $+3.0\sigma$.
3. **Rogue Access Points & Evil Twin Emergence (`NEW_DEVICE_OBSERVED`)**:
   - Indexes observed BSSIDs in a 32-slot LRU table and alerts when an unfamiliar transmitter begins broadcasting.
4. **Traffic Micro-Bursts (`BURST_ANOMALY`)**:
   - Computes peak-to-average frame ratios across sliding 10-second sub-windows to unmask covert low-and-slow reconnaissance scans.
5. **Cryptographic Hash Tampering (`CHAIN_COMPROMISED`)**:
   - Executes recursive verification across all historical evidence blocks; any modified byte or missing block breaks the hash linkage and triggers an alert.
6. **Host-Side Machine Learning Anomalies (`ML_ISOLATION_FOREST`)**:
   - Evaluates multi-dimensional feature vectors against an unsupervised Robust MAD ellipsoidal envelope with explainable feature attribution.

---

## System Architecture Pipeline

```text
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                      ESP32 HARDWARE APPLIANCE CORE                          │
 ├────────────────────────────────────────┬────────────────────────────────────┤
 │           CORE 0 (PRO_CPU)             │          CORE 1 (APP_CPU)          │
 │                                        │                                    │
 │  ┌──────────────────────────────────┐  │  ┌──────────────────────────────┐  │
 │  │ 802.11b/g/n Promiscuous PHY RX   │  │  │ Statistical Feature Engine   │  │
 │  │ (Channel 11, Sub-µs ISR Callback)│  │  │ (10s Window, Welford Z-Score)│  │
 │  └──────────────────┬───────────────┘  │  └──────────────┬───────────────┘  │
 │                     ▼                  │                 ▼                  │
 │  ┌──────────────────────────────────┐  │  ┌──────────────────────────────┐  │
 │  │ Bounded FreeRTOS Ingress Queue   │  │  │ Heuristic Anomaly Detector   │  │
 │  │ (64-slot Ring, Zero Drop Burst)  │──┼─►│ (5 Deterministic Edge Rules) │  │
 │  └──────────────────┬───────────────┘  │  └──────────────┬───────────────┘  │
 │                     ▼                  │                 ▼                  │
 │  ┌──────────────────────────────────┐  │  ┌──────────────────────────────┐  │
 │  │ Frame Metadata Processor         │  │  │ SHA-256 Tamper-Evident Logger│  │
 │  │ (32-Slot LRU Device Hash Table)  │  │  │ (Cryptographic Hash Chain)   │  │
 │  └──────────────────────────────────┘  │  └──────────────┬───────────────┘  │
 │                                        │                 ▼                  │
 │                                        │  ┌──────────────────────────────┐  │
 │                                        │  │ Embedded REST Micro-API      │  │
 │                                        │  │ (Port 80 HTTP, CORS Enabled) │  │
 │                                        │  └──────────────────────────────┘  │
 └────────────────────────────────────────┴─────────────────┬──────────────────┘
                                                            │ JSON Telemetry
                                                            ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                           HOST & ANALYTICS TIER                             │
 ├────────────────────────────┬─────────────────────────────┬──────────────────┤
 │    Interactive Dashboard   │  Streaming Python Collector │ Host-Side ML     │
 │  (Browser / GitHub Pages)  │   (Raw JSONL Data Stream)   │  (Robust MAD/IF) │
 └────────────────────────────┴─────────────────────────────┴──────────────────┘
```

---

## Directory Structure

```text
ForensiTap-ESP32/
│
├── firmware/                 # C++ ESP32 firmware source code
│   └── main/                 # Top-level firmware sketches and execution entry points
│       ├── ForensiTap.ino    # Main application setup() and loop() orchestration
│       ├── system_config.h   # Central hardware definitions and tuning parameters
│       ├── events.h          # Standardized event taxonomy and severity levels
│       ├── module_interface.h# Abstract IModule lifecycle contract
│       ├── diagnostic_logger.h/cpp # Structured serial logging facility
│       ├── network_manager.h/cpp   # Wi-Fi station connectivity and auto-reconnect
│       ├── wifi_credentials.h# Wi-Fi SSID and password configuration
│       ├── wifi_monitor.h/cpp# 802.11 sniffer, metadata extractor, and LRU table
│       ├── feature_engine.h/cpp # 10s sliding-window statistical engine
│       ├── detector.h/cpp    # Deterministic anomaly detection rules engine
│       ├── evidence_logger.h/cpp # SHA-256 cryptographic evidence hash chain
│       └── api_server.h/cpp  # Embedded REST HTTP API server on Port 80
│
├── dashboard/                # Front-end cybersecurity web dashboard
│   ├── index.html            # Multi-tier web app (Overview, Architecture, Dashboard)
│   ├── style.css             # High-contrast cybersecurity theme and responsive CSS
│   ├── app.js                # Dual-mode engine (Live ESP32 polling + Demo Simulator)
│   └── server.py             # Local Python web server (http://localhost:8080)
│
├── laptop/                   # Host-side Python utilities
│   ├── collector/            # Streaming telemetry logger (JSONL storage)
│   ├── ml/                   # Machine learning model training & streaming inference
│   │   ├── train.py          # Pure Python Robust MAD / Ellipsoidal anomaly trainer
│   │   ├── inference.py      # Real-time feature vector scoring CLI
│   │   └── models/           # Persisted anomaly detection model weights
│   ├── analytics/            # Forensic flow analysis and RSSI distribution
│   └── verification/         # Independent cryptographic evidence audit CLI
│
├── datasets/                 # Reference telemetry traces and synthetic attacks
│
├── tests/                    # Comprehensive unit and integration test suite
│   ├── test_metadata_processing.py # LRU table and MAC address sanitization tests
│   ├── test_feature_engine.py      # Welford algorithm and sliding window tests
│   ├── test_detector.py            # Rule evaluation, cooldown, and alert buffer tests
│   ├── test_evidence_logger.py     # SHA-256 chain math and tamper detection tests
│   ├── test_dashboard.py           # Web DOM structure and API endpoint binding tests
│   ├── test_analytics.py           # Collector and forensic analytics pipeline tests
│   ├── test_ml.py                  # Host ML model inference and attribution tests
│   └── stress_test.py              # Multi-threaded concurrent stress test harness
│
├── documentation/            # In-depth architectural & verification reports
│   ├── HOW_IT_WORKS_AND_WHAT_IT_SOLVES.md # Master guide: Concept, problems, and attacks
│   ├── COMPLETE_SYSTEM_ARCHITECTURE.md    # Master architecture: Silicon, memory, and DAG
│   ├── VALIDATION_REPORT.md  # Empirical hardware benchmark & test report
│   ├── LIMITATIONS.md        # Hardware, radio, and protocol constraints
│   ├── USER_GUIDE.md         # Complete installation and operator manual
│   ├── MACHINE_LEARNING.md   # Unsupervised anomaly detection technical paper
│   ├── STRESS_TESTING.md     # Multi-threaded concurrent load benchmark
│   └── API_REFERENCE.md      # REST HTTP API documentation & curl examples
│
├── index.html                # GitHub Pages root redirect entry point
├── .nojekyll                 # GitHub Pages static asset bypass configuration
└── README.md                 # Primary project documentation
```

---

## Quick Start Guide

### 1. Try the Zero-Install Web Simulator
Visit the live interactive simulator hosted on GitHub Pages:  
👉 **[https://marthanda24086.github.io/forensitap-ESP32/](https://marthanda24086.github.io/forensitap-ESP32/)**

Click **"Simulate Deauth Flood"**, **"Simulate Traffic Spike"**, or **"Test Tamper Detection"** to observe real-time graph updates, alert generation, and blockchain verification.

---

### 2. Run the Local Web Dashboard
To run the dashboard locally on your laptop:
```powershell
python dashboard/server.py
```
Open your browser to `http://localhost:8080`.

---

### 3. Flash the Hardware Firmware (ESP32)

#### Prerequisites
- **Hardware:** ESP32 DevKit V1 (ESP32-WROOM-32)
- **Cable:** Micro-USB data cable (connected to laptop COM port)
- **Software:** Arduino IDE 2.x or VS Code with Arduino extension

#### Installation Steps
1. In Arduino IDE, install the **esp32** board platform by Espressif (`v2.0.11` or later).
2. Install the **ArduinoJson** library (`v6.21.3` or later) via Library Manager.
3. Open `firmware/main/ForensiTap.ino`.
4. Configure your Wi-Fi credentials in `firmware/main/wifi_credentials.h`:
   ```cpp
   #define WIFI_SSID     "Your_Network_SSID"
   #define WIFI_PASSWORD "Your_Network_Password"
   ```
5. Select Board: **ESP32 Dev Module** (Flash Frequency: 80MHz, Upload Speed: 921600).
6. Click **Upload**.
7. Open Serial Monitor at **115200 baud** to view real-time diagnostics and the assigned IP address (e.g. `192.168.1.26`).

---

### 4. Execute the Full Automated Test Suite
ForensiTap-ESP32 includes an extensive 29-test unit and regression suite:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```
*Result: 29 tests passed in 0.04s (100% pass rate).*

To execute the multi-threaded concurrent stress test harness:
```powershell
python tests/stress_test.py --mock --cycles 35
```

---

### 5. Run the Host-Side ML Anomaly Detection Engine
Train the unsupervised robust ellipsoidal model on baseline features:
```powershell
python laptop/ml/train.py --input datasets/synthetic_training_data.csv
```
Run real-time inference on live telemetry vectors:
```powershell
python laptop/ml/inference.py --features '{"frame_rate": 320.0, "byte_rate": 65000, "management_frame_ratio": 0.82, "traffic_burst_score": 4.5}'
```

---

## Embedded REST HTTP API Reference

The ESP32 runs a micro-HTTP server on **Port 80**. All responses include CORS headers (`Access-Control-Allow-Origin: *`).

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System uptime, free heap, Wi-Fi channel, RSSI, and firmware version. |
| `GET` | `/api/stats` | Ingested frame counts (Total, Management, Data, Dropped) and live FPS. |
| `GET` | `/api/features` | 10s sliding window feature vector and Welford running baseline statistics. |
| `GET` | `/api/devices` | Active 32-slot LRU tracked transmitter table (MAC, RSSI, packets, role). |
| `GET` | `/api/alerts` | FIFO ring buffer of raised security anomalies and cooldown status. |
| `GET` | `/api/logs` | SHA-256 evidence chain window (Index, timestamp, hashes, descriptions). |
| `GET` | `/api/logs/verify`| On-chip recursive mathematical hash chain audit. |
| `GET` | `/api/export?format=csv` | Download full evidence chain formatted as forensic CSV. |

#### Example: Verify Evidence Chain On-Chip
```bash
curl -s http://192.168.1.26/api/logs/verify | jq .
```
```json
{
  "chain_intact": true,
  "blocks_checked": 18,
  "genesis_hash": "28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1",
  "tip_hash": "031e9f87a19a9ac7925bb750781fe32b919a778c89b21fae39b7dca46798e1f0"
}
```

---

## Hardware Bill of Materials (BOM)

| Component | Function | Model / Spec | Estimated Cost |
| :--- | :--- | :--- | :--- |
| **Microcontroller** | Core processing & 802.11 PHY sniffer | ESP32-WROOM-32 (Xtensa Dual-Core 240MHz, 520KB SRAM) | ~$4.50 |
| **Power Supply / Cable** | System power & serial programming | Standard Micro-USB Cable (5V 1A) | ~$1.00 |
| **Enclosure** *(Optional)* | Physical housing & tamper containment | 3D-Printed PLA or ABS Case | ~$1.50 |
| **Magnetic Sensor** *(Optional)* | Physical case opening detection | Hall Effect Sensor (A3144) on GPIO 4 | ~$0.80 |
| **Total Hardware Cost** | | | **< $10.00** |

---

## Upgrade & Future Extensibility Roadmap

The modular architecture of ForensiTap-ESP32 (`IModule` interface, decoupled queues, and REST API) allows for clean, drop-in upgrades:

### 1. Dual-Band & 5 GHz RF Ingress (Hardware Upgrade)
- **Current:** Single 2.4 GHz radio (Channels 1–13) locked to Channel 11.
- **Upgrade Path:** Incorporate an **ESP32-C6 / ESP32-S3** with Wi-Fi 6 (802.11ax), or attach an external secondary SPI Wi-Fi transceiver (e.g. Wiznet / ATWINC1500) to decouple the promiscuous sniffer completely from the station uplink radio, enabling multi-channel sequential sweeping without network interruption.

### 2. Persistent Non-Volatile Storage (Storage Upgrade)
- **Current:** 32-block in-memory circular evidence buffer retaining recent events across warm reboots.
- **Upgrade Path:** Implement a write-behind flash ring buffer using **LittleFS / SPIFFS** on the ESP32's 4MB SPI flash, or mount an external MicroSD SPI card breakout to store gigabytes of historical tamper-evident records.

### 3. Hardware Cryptographic Security Element (Security Upgrade)
- **Current:** Software-calculated SHA-256 using ESP32 ROM hardware acceleration (`mbedtls_sha256`).
- **Upgrade Path:** Interface an external I2C hardware secure element (**Microchip ATECC608A / OPTIGA Trust M**) to store private keys in secure silicon and sign evidence blocks with hardware-backed **Ed25519 / ECDSA** digital signatures.

### 4. Physical Anti-Tamper Enclosure (Physical Security Upgrade)
- **Current:** Software tamper detection detecting hash alterations.
- **Upgrade Path:** Wire an active micro-switch or Hall-effect magnetic sensor to GPIO 4 with an asynchronous interrupt (`FALLING`). On enclosure breach, trigger an instantaneous `CASE_OPENED_BREACH` event and optionally zeroize volatile cryptographic keys.

### 5. Enterprise SIEM Ingestion (Integration Upgrade)
- **Current:** Pull-based REST HTTP API and CSV export.
- **Upgrade Path:** Implement an asynchronous **Syslog client (RFC 5424)** or **MQTT / Splunk HEC publisher** on Core 1 to stream minted evidence blocks directly into Splunk, Elastic SIEM, or Wazuh.

---

## Technical Documentation Index

For exhaustive technical deep-dives, see the [`documentation/`](documentation/) directory:

- 📖 **[HOW_IT_WORKS_AND_WHAT_IT_SOLVES.md](documentation/HOW_IT_WORKS_AND_WHAT_IT_SOLVES.md)** — Master architectural guide: Problems solved, RF ingress, and attack catalog.
- 📐 **[COMPLETE_SYSTEM_ARCHITECTURE.md](documentation/COMPLETE_SYSTEM_ARCHITECTURE.md)** — Complete hardware specs, dual-core task breakdown, memory allocation, and hash chain DAG.
- 🧪 **[VALIDATION_REPORT.md](documentation/VALIDATION_REPORT.md)** — Empirical benchmarks, frame rates, throughput percentiles, and hardware tests.
- ⚠️ **[LIMITATIONS.md](documentation/LIMITATIONS.md)** — Detailed academic analysis of single-radio coexistence, antenna range, and flash life.
- 🛠️ **[USER_GUIDE.md](documentation/USER_GUIDE.md)** — Comprehensive operator manual: Flashing, dashboard setup, API commands, and troubleshooting.
- 🤖 **[MACHINE_LEARNING.md](documentation/MACHINE_LEARNING.md)** — Mathematical formulation of host-side unsupervised anomaly detection.
- ⚡ **[STRESS_TESTING.md](documentation/STRESS_TESTING.md)** — Multi-threaded concurrent stress test results and memory leak analysis.
- 📡 **[API_REFERENCE.md](documentation/API_REFERENCE.md)** — Complete JSON schema and curl examples for all REST endpoints.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details. Open for academic research, education, and community extension.
