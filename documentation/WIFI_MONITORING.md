# Stage 8: Wi-Fi Promiscuous-Mode Monitoring

## 1. Overview

**Stage 8** implements the central embedded monitoring engine of **ForensiTap-ESP32**: **`ForensiTapWifiMonitor`** (`firmware/wifi_monitor/wifi_monitor.cpp` and `wifi_monitor.h`).

The module places the ESP32 Wi-Fi baseband into **promiscuous mode**, intercepting raw IEEE 802.11 frames circulating over the air. It extracts critical frame-level metadata and pushes structured observations into a bounded FreeRTOS ring queue for downstream anomaly detection and forensic logging.

---

## 2. Promiscuous Mode Architecture

```
                                  [ AIR INTERFACE (2.4 GHz) ]
                                               |
                                               v
                             +-----------------------------------+
                             |  ESP32 RF Frontend & Baseband     |
                             +-----------------------------------+
                                               |
                                               v
                             +-----------------------------------+
                             | esp_wifi Hardware Packet Filter   |
                             | (WIFI_PROMIS_FILTER_MASK_MGMT     |
                             |  | WIFI_PROMIS_FILTER_MASK_DATA)  |
                             +-----------------------------------+
                                               |
                                               v
                             +-----------------------------------+
                             | promiscuousRxCallback (IRAM_ATTR) |
                             | - Increments frame counters       |
                             | - Extracts 802.11 MAC headers     |
                             | - Zero heap allocation (< 5 µs)   |
                             +-----------------------------------+
                                               | (xQueueSendFromISR)
                                               v
                             +-----------------------------------+
                             | Bounded FreeRTOS Queue (64 slots) |
                             | (Discards + counts if full)       |
                             +-----------------------------------+
                                               | (xQueueReceive)
                                               v
                             +-----------------------------------+
                             | ForensiTap Core Loop (app_main)   |
                             | - Feeds /api/stats                |
                             | - Updates System Telemetry        |
                             +-----------------------------------+
```

---

## 3. Strict Real-Time Embedded Constraints

To maintain system stability and prevent hardware watchdog resets (`WDT`):
1. **ISR Attribute (`IRAM_ATTR`):** The RX callback is mapped to internal instruction RAM (IRAM) so that execution never stalls on SPI flash cache misses.
2. **Sub-Microsecond Execution:** The callback only parses the first 24 bytes of the 802.11 MAC header. It performs **no** dynamic memory allocation (`malloc`/`new`), no string operations, and no serial logging.
3. **Bounded FreeRTOS Queue:** Observations are transferred via `xQueueSendFromISR()` to a fixed-size queue (64 slots). If burst traffic saturates the queue, incoming frames are gracefully dropped and recorded in `s_droppedFrames`.

---

## 4. Supported Metadata Extraction

For every observed frame, the following metadata is extracted into a fixed-size [`FrameObservation`](file:///d:/forensitap-ESP32/firmware/main/ForensiTap/wifi_monitor.h#L20) struct:

| Metadata Field | Source | Description |
| :--- | :--- | :--- |
| `timestampMs` | Monotonic clock | System uptime in milliseconds when frame was received |
| `length` | `pkt->rx_ctrl.sig_len` | Total wire length of the 802.11 frame in bytes |
| `rssi` | `pkt->rx_ctrl.rssi` | Received signal strength indicator in dBm |
| `channel` | `pkt->rx_ctrl.channel` | 2.4 GHz radio channel on which the frame was captured |
| `frameType` | `wifi_promiscuous_pkt_type_t` | Frame classification: `MGMT` (0), `CTRL` (1), `DATA` (2) |
| `frameSubtype` | Byte 0 (`payload[0] & 0xF0 >> 4`) | Subtype (e.g., Beacon `0x08`, Probe Request `0x04`, Deauth `0x0C`) |
| `retry` | Byte 1 (`payload[1] & 0x08`) | 802.11 retransmission flag |
| `sourceMac` | Bytes 10–15 (`Addr 2`) | MAC address of the transmitting device |
| `destMac` | Bytes 4–9 (`Addr 1`) | MAC address of the destination / receiver |

---

## 5. Fixed-Channel Experiment & Radio Coexistence

### 5.1 Channel Selection: Channel 11
- Your Wi-Fi Access Point operates on **Channel 11** (reported by `ForensiTapNetworkManager` during Stage 6).
- `ForensiTapWifiMonitor` is explicitly configured to listen on **Channel 11** (`g_config.defaultWifiChannel = 11;`).

### 5.2 Coexistence Behavior
- Because both the Station connection (`WIFI_STA`) and the promiscuous filter operate on **Channel 11**, the ESP32 maintains simultaneous connectivity:
  - It handles incoming HTTP requests on port 80 (`/api/stats`, `/api/health`).
  - It captures all ambient 802.11 frames on Channel 11 over the air.
- **Limitation:** In this connected mode, frames transmitted on other channels (e.g., Channel 1 or 6) are invisible to the radio. Dedicated multi-channel monitoring will be introduced via channel scanning in subsequent stages.

---

## 6. Verification & Testing Procedure

### Step 1: Upload Stage 8 Firmware
1. Open `D:\forensitap-ESP32\firmware\main\ForensiTap\ForensiTap.ino` in Arduino IDE 2.x.
2. Upload (`Ctrl + U`) to your ESP32 board.
3. Open Serial Monitor at **115200 baud**.

### Step 2: Observe Serial Monitor Telemetry
Expected output:
```text
[      1054] [INFO ] [SYS ] Subsystem [NET] initialization SUCCESS
[      1055] [INFO ] [SYS ] Subsystem [MON] initialization SUCCESS
[      1056] [INFO ] [SYS ] Subsystem [API] initialization SUCCESS
[      1057] [INFO ] [MON ] Starting 802.11 promiscuous mode on Channel 11...
[      1060] [INFO ] [MON ] Promiscuous frame capture ACTIVE on Channel 11
...
[      4000] [INFO ] [LIV ] [HEARTBEAT] ForensiTap | WIFI_CONNECTED | MON_ACTIVE | API_ACTIVE | Frames: 47 (23.5 fps) | Uptime: 4 s | Heap: 228412 B

---------------- [SYSTEM TELEMETRY REPORT] ----------------
Uptime           : 10000 ms (10 sec)
Operating State  : Mode 2 | Health: OPTIMAL
Memory Available : 228412 bytes dynamic heap
Events Processed : 1 logged
Frames Ingested  : 184 frames | 0 dropped
----------------------------------------------------------
  +-- [Wi-Fi Monitor Subsystem: MON]
  |   Promiscuous Mode : ACTIVE (Channel 11)
  |   Observed Total   : 184 frames (18.4 fps)
  |   Management Frames: 42
  |   Data Frames      : 142
  |   Control Frames   : 0
  |   Queue Dropped    : 0 frames
  +------------------------------------
```

### Step 3: Verify Live API Response
In your laptop browser or PowerShell terminal, query the stats endpoint:
```powershell
Invoke-RestMethod -Uri "http://192.168.1.26/api/stats"
```
Expected JSON:
```json
{
  "monitoring_status": "ACTIVE",
  "active_channel": 11,
  "total_observed_frames": 248,
  "current_frame_rate": 24.8,
  "unique_observed_devices": 0,
  "management_frame_count": 58,
  "data_frame_count": 190,
  "control_frame_count": 0,
  "dropped_frames_count": 0
}
```
