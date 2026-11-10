# Implementation Log
**ForensiTap-ESP32 Autonomous Premium Digital Product Development**

---

## 1. Executive Summary of Changes
Transformed the ForensiTap-ESP32 project from a prototype dashboard into a complete, award-winning, agency-grade cyber-physical product experience. Upgraded both the embedded firmware software engine on the ESP32 and the web-based tactical SOC console.

---

## 2. Software & Engine Engineering Modifications (Firmware & Backend)

### A. Granular 802.11 Frame Subtype Ingestion
* **Files:** `firmware/feature_engine/feature_engine.h`, `feature_engine.cpp`, `firmware/wifi_monitor/wifi_monitor.cpp`
* **Changes:** 
  - Extended `WindowBucket` to track specific 802.11 subtypes extracted in the promiscuous RX callback: Deauth (`0x0C`), Disassoc (`0x0A`), Beacon (`0x08`), Probe Request (`0x04`).
  - Added discrete feature vectors: `deauthRate`, `disassocRate`, `beaconRate`, and `deauthRatio`.
  - Replaced coarse `managementRatio` approximations with high-precision subtype tracking.

### B. Adaptive EWMA Baseline Profile
* **Files:** `firmware/feature_engine/feature_engine.cpp`
* **Changes:**
  - Implemented an Exponentially Weighted Moving Average baseline ($\alpha = 0.05$) operating alongside Welford's algorithm.
  - Resolves the baseline "freezing" flaw where thousands of accumulated historical windows made the running mean inflexible to legitimate day/night diurnal variations.

### C. Targeted Deauth Flood & Evil Twin Detection Rules
* **Files:** `firmware/main/events.h`, `firmware/detector/detector.h`, `detector.cpp`
* **Changes:**
  - Added `EventType::DEAUTH_FLOOD_ATTACK` and `EventType::EVIL_TWIN_SUSPECTED`.
  - Rule 6 (`checkRule6DeauthFlood`): Directly triggers on `deauthRate >= 3.0 fps` or `deauthRatio >= 15%`.
  - Rule 7 (`notifyRssiAnomaly`): Monitors consecutive AP sightings and triggers on instantaneous RSSI disparities ($\ge 28\text{ dBm}$) indicating a cloned rogue transmitter.

### D. Embedded Edge ML Classifier on Core 1
* **Files:** `firmware/detector/edge_ml_classifier.h` (synced to `firmware/main/` and `firmware/main/ForensiTap/`)
* **Changes:**
  - Implemented an ultra-lightweight, zero-heap decision tree classifier running directly in C++ on Xtensa Core 1.
  - Scores multi-dimensional feature vectors in $<1\text{ ms}$ with discrete confidence scores and attribution root causes (`BENIGN`, `DEAUTH_FLOOD`, `BURST_SPIKE`, `MGMT_STORM`, `RECON_SCAN`).

### E. Telemetry Endpoints & REST API Synchronization
* **Files:** `firmware/api_server/api_server.cpp`
* **Changes:**
  - Updated `/api/features` JSON response with `deauth_rate`, `disassoc_rate`, `deauth_ratio`, `beacon_rate`, and `ewma_mean_frame_rate`.
  - Synchronized firmware across standalone modules, `firmware/main/`, and Arduino sketch directory `firmware/main/ForensiTap/`.

---

## 3. UI/UX & Web Application Modifications

### A. Information Architecture & Navigation
* **Files:** `dashboard/index.html`, `dashboard/style.css`, `dashboard/app.js`
* **Changes:**
  - Designed 5 distinct views:
    1. **SOC Cockpit:** High-density operational dashboard with real-time telemetry, live traffic chart, radar preview, explainable incident cards, and LRU transmitter table.
    2. **Airspace Radar:** Full-screen dedicated polar radio constellation.
    3. **Evidence Explorer:** Visual blockchain with interactive tamper verification sandbox.
    4. **Architecture:** Detailed 7-tier FreeRTOS pipeline and hardware coexistence breakdown.
    5. **Docs & Specs:** Evaluation overview, threat taxonomy, and \$10 hardware bill of materials.

### B. Explainable Incident Response Cards
* **Files:** `dashboard/app.js`, `dashboard/style.css`
* **Changes:**
  - Replaced raw mathematical text strings with structured incident cards featuring threat severity badges (`CRITICAL`, `HIGH`, `MEDIUM`, `INFO`), human-understandable descriptions, attacker intent explanations, and recommended forensic remediations.

### C. Interactive 2.4 GHz Airspace Radar Canvas
* **Files:** `dashboard/app.js`, `dashboard/style.css`
* **Changes:**
  - Built an animated Canvas 2D polar radar with a continuous rotating sweep beam.
  - Placed transmitter nodes by RSSI distance ($-30$ to $-90\text{ dBm}$) with role color-coding (Cyan for AP, Green for STA, Red for Rogue/Attacker).
  - Added interactive mouse hover HUD inspection: displays a floating glass card with MAC address, vendor OUI, RSSI, and observed frame count.

### D. Visual SHA-256 Blockchain Explorer & Tamper Sandbox
* **Files:** `dashboard/app.js`, `dashboard/style.css`
* **Changes:**
  - Visualized chronological block sequence with connected hash arrows.
  - Built an interactive **"Simulate Tamper"** sandbox button: introduces 1-byte corruption into Block #1 to visually demonstrate downstream hash failure (turning links RED) and proving cryptographic tamper-evidence in legal proceedings.
  - One-click browser CSV chain exporter.

### E. WebSerial API Integration (Browser USB Connection)
* **Files:** `dashboard/app.js`
* **Changes:**
  - Implemented native WebSerial streaming via `navigator.serial.requestPort()`.
  - Enables direct plug-and-play USB connection for Chrome and Edge users without configuring local network IP routing.

### F. Performance, Assets & Mobile Responsiveness
* **Files:** `dashboard/style.css`, `dashboard/index.html`, `favicon.ico`
* **Changes:**
  - Generated dedicated high-contrast cyber lightning bolt favicon (`favicon.ico`) resolving all 404 requests.
  - Added responsive media queries supporting viewports from 1920px wide down to 375px mobile screens.
  - Zero heavy external JavaScript dependencies; uses native Web APIs, lightweight Chart.js, and Canvas 2D.
