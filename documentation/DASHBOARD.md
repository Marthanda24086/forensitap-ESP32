# ForensiTap-ESP32: Front-End Web Dashboard

## 1. Overview

The **ForensiTap-ESP32 Live Web Dashboard** (Stage 13) provides an interactive, dark-themed cybersecurity command interface for monitoring wireless 802.11 traffic, real-time statistical anomaly metrics, LRU device tracking, and cryptographic SHA-256 evidence verification.

The dashboard runs entirely client-side, communicating with the ESP32 REST API (`http://192.168.1.26`) asynchronously via CORS-enabled HTTP endpoints. It can be loaded directly from the filesystem (`file:///.../dashboard/index.html`) or hosted through the local Python server (`dashboard/server.py`).

---

## 2. Interface Architecture

```mermaid
flowchart TD
    subgraph Client [Web Browser / Laptop Dashboard]
        UI[index.html / style.css]
        APP[app.js Orchestrator]
        CHART[Chart.js Time-Series Engine]
    end

    subgraph Hardware [ESP32 Appliance (192.168.1.26:80)]
        API[ForensiTapApiServer]
        H_END[/api/health]
        S_END[/api/stats]
        F_END[/api/features]
        D_END[/api/devices]
        A_END[/api/alerts]
        L_END[/api/logs]
        V_END[/api/logs/verify]
        E_END[/api/export]
    end

    APP -->|Polling every 1-5s| H_END & S_END & F_END & D_END & A_END & L_END
    UI -->|Audit Chain Button| V_END
    UI -->|Export CSV Button| E_END
    APP --> CHART
    CHART --> UI
```

---

## 3. Key Components & Visual Panels

1. **Top Header & Appliance Controls:**
   - **Appliance Target IP:** Configurable input field (defaults to `http://192.168.1.26`, persisted in `localStorage`).
   - **Polling Interval Selector:** Select between 1s, 2s, or 5s refresh rates.
   - **Pause/Resume Button:** Freezes live queries for inspection.
   - **Connection Status Badge:** Dynamic latency pill displaying ping round-trip time (`ms`) or `OFFLINE` status.

2. **Top KPI Cards:**
   - **System Uptime & Firmware Version:** Current operational duration and firmware tag.
   - **Observed Traffic:** Real-time frame rate (FPS) and aggregate frames observed since boot.
   - **Active Radio Channel & Signal RSSI:** Promiscuous monitoring channel and link strength.
   - **Tracked Peers & Queue Health:** Active tracked MAC entries and dropped packet count.
   - **Evidence Chain Status:** Minted block tally and tamper-evident validity badge.

3. **Live 802.11 Traffic Time-Series Chart:**
   - 30-sample sliding window graph rendered via Chart.js.
   - Plots live frame rate against Welford's adaptive baseline running mean to visually spotlight traffic spikes and bursts.

4. **Active Tracked Devices Table:**
   - Displays all currently observed MAC addresses in the 32-slot LRU eviction table.
   - Device role badges (`AP` vs. `STA`).
   - Packet counts, signal RSSI color-coded by strength, and last seen timestamps.

5. **SHA-256 Tamper-Evident Evidence Log:**
   - Renders the most recent evidence blocks held in the sliding memory window.
   - Monospace preview of `prev_hash` and `block_hash`.
   - **One-Click Audit Button ("Audit Chain Now"):** Calls `/api/logs/verify` and alerts if any cryptographic hash link is broken or modified.
   - **One-Click CSV Export ("Export CSV"):** Downloads a comma-separated audit ledger.

6. **Statistical Feature Vector Inspection:**
   - Window FPS, byte throughput, average frame size, management frame ratio %, burstiness score, and Welford baseline $(\mu \pm \sigma, Z\text{-score})$.

7. **Real-Time Security Alerts Feed:**
   - Live stream of anomaly events classified by severity (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).

---

## 4. How to Launch & Use the Dashboard

### Method A: Local Python Server (Recommended)
From the repository root:
```bash
python dashboard/server.py
```
This starts a lightweight web server on port 8080 and automatically launches your default web browser to `http://localhost:8080`.

### Method B: Direct File Opening
Double-click `dashboard/index.html` or open it directly in Google Chrome, Microsoft Edge, or Firefox.

### Method C: Custom Port
```bash
python dashboard/server.py --port 9000
```
