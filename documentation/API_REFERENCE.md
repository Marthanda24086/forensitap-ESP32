# ForensiTap-ESP32: REST HTTP API Reference

## 1. Overview

**Stage 7** implements a lightweight REST HTTP API on the **ForensiTap-ESP32** appliance using the Arduino ESP32 `WebServer` library on standard port `80`.

The API serves real-time health telemetry, frame statistics, device observations, security alerts, statistical feature vectors, and tamper-evident forensic logs to the host workstation and web dashboard.

---

## 2. API Design & Security Principles

1. **Read-Only Inspection:** The API operates as a passive observability interface (`HTTP GET`). It contains no mutation endpoints, preventing unauthorized state modification over the air.
2. **Credential Sanitization:** Sensitive information (such as `WIFI_PASSWORD` in `wifi_credentials.h`) is strictly omitted from all response schemas.
3. **CORS Enabled:** Cross-Origin Resource Sharing (`Access-Control-Allow-Origin: *`) headers are automatically attached to all JSON responses and preflight `OPTIONS` requests, enabling the local browser dashboard (`dashboard/index.html`) to query the appliance directly.
4. **Bounded Memory Allocation:** Fixed-size buffers (`snprintf`) are used for JSON serialization to avoid heap fragmentation and prevent Out-Of-Memory crashes.
5. **Auto-Binding Lifecycle:** The HTTP server automatically activates as soon as `ForensiTapNetworkManager` secures an IP lease from DHCP and pauses gracefully if Wi-Fi disconnects.

---

## 3. Endpoint Reference

Base URL: `http://<ESP32_IP>/` (e.g., `http://192.168.1.26/`)

### 3.1 `GET /`
- **Purpose:** Appliance identity verification and service discovery.
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "app": "ForensiTap-ESP32",
    "version": "1.0.0-stage5-arch",
    "status": "ONLINE",
    "docs": "/api/health"
  }
  ```

---

### 3.2 `GET /api/health`
- **Purpose:** Core embedded health telemetry, uptime, memory, and Wi-Fi link quality.
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "status": "OPTIMAL",
    "uptime_ms": 208120,
    "uptime_sec": 208,
    "firmware_version": "1.0.0-stage5-arch",
    "hardware": "ESP32 DevKit V1 (ESP32-WROOM-32)",
    "free_heap_bytes": 234028,
    "wifi_connected": true,
    "ip_address": "192.168.1.26",
    "wifi_channel": 11,
    "rssi_dbm": -57
  }
  ```

---

### 3.3 `GET /api/stats`
- **Purpose:** 802.11 frame capture counters, data vs. management distribution, and dropped packet metrics.
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "monitoring_status": "STANDBY",
    "active_channel": 11,
    "total_observed_frames": 0,
    "current_frame_rate": 0.0,
    "unique_observed_devices": 0,
    "management_frame_count": 0,
    "data_frame_count": 0,
    "dropped_frames_count": 0
  }
  ```

---

### 3.4 `GET /api/devices`
- **Purpose:** Table of observed MAC addresses, packet counts, and signal strength.
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "count": 0,
    "devices": []
  }
  ```

---

### 3.5 `GET /api/alerts`
- **Purpose:** Bounded buffer of detected security anomalies (traffic spikes, deauth floods, physical tampering).
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "count": 0,
    "alerts": []
  }
  ```

---

### 3.6 `GET /api/features`
- **Purpose:** Real-time statistical feature vector calculated by the sliding window engine (Stage 10).
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "window_duration_sec": 10,
    "frame_rate": 0.0,
    "byte_rate": 0.0,
    "average_frame_size": 0.0,
    "unique_peers": 0,
    "management_frame_ratio": 0.0,
    "traffic_burst_score": 0.0
  }
  ```

---

### 3.7 `GET /api/logs`
- **Purpose:** Sequential forensic event log records.
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "count": 1,
    "logs": [
      {
        "seq": 1,
        "timestamp": 1055,
        "event": "SYSTEM_BOOT",
        "severity": "INFO",
        "source": "SYS",
        "description": "ForensiTap v1.0.0-stage5-arch initialized"
      }
    ]
  }
  ```

---

### 3.8 `GET /api/logs/verify`
- **Purpose:** Cryptographic status of the on-device SHA-256 evidence chain (Stage 12).
- **Response Format:** `application/json`
- **Example Response:**
  ```json
  {
    "chain_verified": true,
    "records_verified": 1,
    "latest_record_hash": "GENESIS_INITIALIZED_STAGE7",
    "status": "VALID"
  }
  ```

---

### 3.9 `GET /api/export`
- **Purpose:** Download bounded forensic records in either JSON or CSV format.
- **Query Parameters:**
  - `format=json` (default): Emits structured JSON export.
  - `format=csv`: Emits comma-separated values with `Content-Disposition: attachment`.
- **Example Response (`?format=csv`):**
  ```text
  seq,timestamp_ms,event_type,severity,source,description
  1,1055,SYSTEM_BOOT,INFO,SYS,ForensiTap initialized
  ```

---

## 4. How to Test Every Endpoint Independently

Once uploaded to your ESP32 (assigned IP: `192.168.1.26` from your Stage 6 test):

### Method A: Using a Web Browser
Open any browser on your laptop (connected to the same Wi-Fi network) and navigate to:
- `http://192.168.1.26/api/health`
- `http://192.168.1.26/api/stats`
- `http://192.168.1.26/api/devices`
- `http://192.168.1.26/api/alerts`
- `http://192.168.1.26/api/features`
- `http://192.168.1.26/api/logs`
- `http://192.168.1.26/api/logs/verify`
- `http://192.168.1.26/api/export?format=json`
- `http://192.168.1.26/api/export?format=csv`

### Method B: Using PowerShell on Your Windows Laptop
Run in a PowerShell terminal:
```powershell
# Test health endpoint
Invoke-RestMethod -Uri "http://192.168.1.26/api/health"

# Test stats endpoint
Invoke-RestMethod -Uri "http://192.168.1.26/api/stats"

# Test logs endpoint
Invoke-RestMethod -Uri "http://192.168.1.26/api/logs"

# Test export endpoint
Invoke-RestMethod -Uri "http://192.168.1.26/api/export?format=json"
```
