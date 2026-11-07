# ForensiTap-ESP32: Complete User & Operator Guide

## 1. System Requirements & Hardware Setup

### Hardware Needed
- **ESP32 DevKit V1** (ESP32-WROOM-32 with micro-USB port).
- **USB Data Cable** (Micro-USB to USB-A/C, ensuring 4-wire data capability, not charge-only).
- **Host Laptop** (Windows, Linux, or macOS with Python 3.8+ installed).

### Pinout Configuration
- **USB Power & Programming:** Micro-USB port on ESP32 DevKit V1.
- **Onboard Status LED:** GPIO 2 (toggles or illuminates during active telemetry).
- **UART Communication:** 115200 baud over virtual COM port via CP2102/CH340 USB-UART bridge.

---

## 2. Firmware Compilation & Flashing

### Method A: Arduino IDE 2.x
1. Open Arduino IDE 2.x.
2. Go to **File $\to$ Open** and select:
   ```text
   d:\forensitap-ESP32\firmware\main\ForensiTap\ForensiTap.ino
   ```
3. Set Board to **DOIT ESP32 DEVKIT V1**.
4. Configure Wi-Fi Credentials in `wifi_credentials.h` if changing networks:
   ```cpp
   #define FORENSITAP_WIFI_SSID     "YourSSID"
   #define FORENSITAP_WIFI_PASSWORD "YourPassword"
   ```
5. Select your active COM port (e.g., `COM3`, `COM4`).
6. Click **Upload** (`Ctrl + U`).
7. Open **Serial Monitor** at **115200 baud**.

### Method B: Arduino CLI
From a terminal prompt:
```bash
arduino-cli compile --fqbn esp32:esp32:esp32doit-devkit-v1 "firmware/main/ForensiTap"
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32doit-devkit-v1 "firmware/main/ForensiTap"
```

---

## 3. Launching the Live Cybersecurity Web Dashboard

1. Ensure the ESP32 is powered on and connected to your Wi-Fi network (verified IP: `192.168.1.26`).
2. On your laptop, open a terminal in the project root and run:
   ```bash
   python dashboard/server.py
   ```
3. Your default web browser will automatically open `http://localhost:8080`.
4. The dashboard will connect to the ESP32, displaying:
   - Live 802.11 Frame Rate line graph.
   - Active Tracked Devices table with MAC, roles, and RSSI.
   - Cryptographic Evidence Chain table.
   - "Audit Chain Now" and "Export CSV" buttons.

---

## 4. Running the Host-Side Streaming Collector

To record a continuous forensic capture session to disk:
```bash
# Ingest live telemetry and evidence blocks into datasets/sessions/
python laptop/collector/collector.py

# Ingest with 1-second polling for a fixed 60-second capture
python laptop/collector/collector.py --interval 1.0 --duration 60
```
This saves structured `.jsonl` files in `datasets/sessions/session_YYYYMMDD_HHMMSS/`:
- `telemetry.jsonl`
- `devices.jsonl`
- `evidence_chain.jsonl`
- `session_meta.json`

---

## 5. Performing Offline Forensic Traffic Analysis

To generate an executive statistical report from a recorded capture session:
```bash
# Analyze the most recently captured session
python laptop/analytics/traffic_analysis.py --latest

# Analyze a specific session folder
python laptop/analytics/traffic_analysis.py --session-dir datasets/sessions/session_20261107_221713
```
This prints an analytical profile including:
- Frame rate mean, median, standard deviation, and peak rates.
- Frame composition (Management vs. Data packets).
- Top transmitting MAC entities and signal strength profiles.
- Cryptographic hash chain audit status.
- Export of `analysis_summary.json` for archival.

---

## 6. Verifying Evidence Chain & Detecting Tampering

### On-Demand Independent Verification Script
```bash
# Verify the live ESP32 in-memory hash chain over Wi-Fi
python laptop/verification/verify_logs.py --url http://192.168.1.26/api/logs

# Demonstrate simulated adversary tamper detection
python laptop/verification/verify_logs.py --tamper-demo
```

### Direct REST API Query
From PowerShell or curl:
```bash
# Check on-chip cryptographic verification
curl.exe -s http://192.168.1.26/api/logs/verify

# Download raw evidence chain
curl.exe -s http://192.168.1.26/api/logs

# Export CSV evidence
curl.exe -s "http://192.168.1.26/api/export?format=csv" -o evidence.csv
```

---

## 7. Troubleshooting & Diagnostics

| Symptom | Probable Cause | Corrective Action |
|---|---|---|
| **Serial Monitor shows garbled text** | Baud rate mismatch | Ensure Serial Monitor is set strictly to `115200 baud`. |
| **Wi-Fi status: DISCONNECTED** | Incorrect SSID/password or 5 GHz AP | Verify credentials in `wifi_credentials.h`. Note that ESP32 only connects to 2.4 GHz networks. |
| **Dashboard shows OFFLINE** | ESP32 IP address changed | Check Serial Monitor for current DHCP lease and update the "Appliance" IP field in dashboard top bar. |
| **High Dropped Frame Count** | Channel traffic exceeding queue | Ensure CPU is running at 240 MHz. Avoid high-frequency simultaneous curl loops ($> 15\,\text{req/s}$). |
| **Hash Verification Fails** | Data tampering or link break | Inspect reported `failed_index` in `/api/logs/verify` or run `verify_logs.py` to identify the altered block. |
