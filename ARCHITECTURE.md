# System Architecture & Technical Specifications
**ForensiTap-ESP32 Autonomous Premium Digital Product**

---

## 1. System Topology Overview
The ForensiTap-ESP32 digital product connects three coordinated tiers:
1. **Edge Hardware Sensor (ESP32 PHY Promiscuous Sniffer)**: Dual-Core Xtensa running FreeRTOS at 240MHz.
2. **Telemetry & Cryptographic Engine**: In-memory ring buffers, Welford/EWMA feature extractor, deterministic rule engine + Edge Decision Tree, and SHA-256 evidence chain.
3. **Web-Based Cyber SOC Console**: High-performance client-side application running in modern web browsers, supporting both network HTTP REST polling and direct WebSerial USB streaming.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM ARCHITECTURE MAP                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ┌───────────────────────────┐                     ┌──────────────────────────────┐   │
│   │   ESP32 HARDWARE SENSOR   │                     │      WEB CLIENT CONSOLE      │   │
│   │                           │                     │                              │   │
│   │  Core 0 (PRO_CPU):        │   Wi-Fi REST /      │  - SOC Cockpit Dashboard     │   │
│   │   - Promiscuous RX ISR    │   WebSerial Stream  │  - 2.4 GHz Airspace Radar    │   │
│   │   - 64-slot Ring Queue    ├────────────────────►│  - Explainable Threat Cards  │   │
│   │                           │                     │  - SHA-256 Chain Explorer    │   │
│   │  Core 1 (APP_CPU):        │                     │  - Chart.js Telemetry Graph  │   │
│   │   - Feature Engine (EWMA) │                     │  - Attack Simulation Suite   │   │
│   │   - Anomaly Detector & ML │                     └──────────────────────────────┘   │
│   │   - SHA-256 Chain Minting │                                                        │
│   │   - REST API Web Server   │                                                        │
│   └───────────────────────────┘                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Telemetry Endpoints & Data Contracts

| Method | Endpoint | Description | Payload Structure |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System status, uptime, memory, Wi-Fi channel | `{"status":"OPTIMAL","uptime_sec":120,"free_heap_bytes":184200,...}` |
| `GET` | `/api/stats` | Frame counters, dropped frames, current FPS | `{"monitoring_status":"ACTIVE","active_channel":11,"current_frame_rate":94.5,...}` |
| `GET` | `/api/features` | 10s rolling feature vector & baseline profile | `{"frame_rate":94.5,"deauth_rate":0.0,"deauth_ratio":0.0,"baseline":{...}}` |
| `GET` | `/api/devices` | Active 32-slot LRU tracked transmitter table | `{"count":6,"devices":[{"mac":"...","last_rssi_dbm":-54,"is_ap":true},...]}` |
| `GET` | `/api/alerts` | Stored security alerts & anomalies | `{"count":3,"alerts":[{"event_id":1,"type":"DEAUTH_FLOOD_ATTACK",...}]}` |
| `GET` | `/api/logs` | SHA-256 cryptographic evidence chain | `{"chain_valid":true,"genesis_hash":"...","tip_hash":"...","blocks":[...]}` |
| `GET` | `/api/logs/verify`| Real-time mathematical hash audit | `{"is_valid":true,"blocks_checked":16,"failed_index":0,"reason":"OK"}` |
| `GET` | `/api/export` | Download complete evidence chain as CSV | `Index,Timestamp_MS,Event_Type,Severity,Description,Prev_Hash,Block_Hash\n` |

---

## 3. Cryptographic Evidence Chain Specification
Every forensic incident is sealed in an append-only cryptographic structure:
$$\text{Block\_Hash}_i = \text{SHA-256}(\text{Index}_i \parallel \text{Timestamp}_i \parallel \text{EventType}_i \parallel \text{Severity}_i \parallel \text{Description}_i \parallel \text{Block\_Hash}_{i-1})$$

* **Genesis Block ($i=0$):** Anchored with `prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"`.
* **Tamper-Evident Invariant:** If any byte of historical block $k$ ($k < n$) is modified, all subsequent hashes $\text{Block\_Hash}_{k \dots n}$ fail mathematical validation.
* **Legal Admissibility:** Establishes digital chain-of-custody satisfying Federal Rules of Evidence (FRE 902(13)/(14)) for electronic records.

---

## 4. Frontend Execution Architecture
* **HTML5 Semantic Structure:** Clean separation of concerns with progressive enhancement.
* **Canvas 2D Rendering Engine:** High-performance polar coordinate mapping for RF signal strength ($r \propto -1 \times \text{RSSI}$) and rotating sweep line running at 60 FPS via `requestAnimationFrame`.
* **Chart.js Integration:** Dual-series line charts with dynamic rolling buffers (30 historical data points) visualizing instantaneous FPS vs. Adaptive EWMA baseline curves.
* **WebSerial API Integration:** Hardware-direct binary/text streaming using `navigator.serial` at 115200 baud for plug-and-play USB operation.
