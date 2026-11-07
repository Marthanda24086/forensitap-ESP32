# Stage 9: Frame Metadata Processing & Device Tracking

## 1. Overview

**Stage 9** introduces the internal metadata consumption pipeline for **ForensiTap-ESP32**. 

While Stage 8 established raw 802.11 promiscuous frame reception into a bounded FreeRTOS queue, Stage 9 dequeues and translates these observations into structured, memory-bounded forensic intelligence:
- Frame validation and sanitization.
- Safe extraction of transmitting and receiving MAC addresses.
- Multi-dimensional device tracking (packet counts, uptime span, RSSI envelope).
- Least-Recently-Used (LRU) memory-bounded device eviction.
- Direct integration into the REST API (`GET /api/devices` and `GET /api/stats`).

---

## 2. Metadata Processing Pipeline

```
 [ FreeRTOS Observation Queue ]
               |
               v (xQueueReceive)
 +-----------------------------+
 | Frame Validation Stage      |
 | - Length bounds: [10, 2346] |----(Invalid)----> Increment s_malformedFrames & Discard
 | - Frame type: [0, 3]        |
 +-----------------------------+
               | (Valid)
               v
 +-----------------------------+
 | Address Sanitization Stage  |
 | - Reject all zeros          |----(Multicast/Broadcast)----> Bypass Device Table
 | - Reject broadcast (FF:..FF)|
 | - Reject multicast (bit 0=1)|
 +-----------------------------+
               | (Valid Unicast)
               v
 +-----------------------------------------------------------+
 | Bounded Device Table (32 Entries, LRU Eviction)           |
 | - Matches MAC -> Updates frameCount, lastSeen, RSSI envelope|
 | - New MAC & Space available -> Allocates new slot         |
 | - New MAC & Table full -> Evicts oldest inactive entry    |
 +-----------------------------------------------------------+
               |
               v
 [ REST HTTP API: GET /api/devices & GET /api/stats ]
```

---

## 3. Data Structures

### 3.1 Device Record (`DeviceRecord`)
Each tracked station or access point occupies a fixed 24-byte footprint:

```cpp
struct DeviceRecord {
    uint8_t  mac[6];          // Canonical 48-bit physical address
    uint32_t frameCount;      // Number of frames observed from this MAC
    uint32_t firstSeenMs;     // Uptime timestamp when first seen
    uint32_t lastSeenMs;      // Uptime timestamp of most recent frame
    int8_t   lastRssi;        // Most recent signal strength in dBm
    int8_t   minRssi;         // Weakest signal observed
    int8_t   maxRssi;         // Strongest signal observed
    bool     isAccessPoint;   // True if observed transmitting Beacons or Probe Responses
    bool     inUse;           // Active slot flag in fixed table
};
```

### 3.2 Memory Safety: Bounded LRU Table
- **Capacity:** Fixed at **32 devices** (`MAX_TRACKED_DEVICES`). Total static memory footprint is under **1 KB**.
- **Zero Heap Allocation:** No dynamic `new` or `malloc` is executed during device table updates, preventing heap fragmentation.
- **LRU Eviction:** When a 33rd unique wireless device is encountered, the algorithm iterates across the table to identify the entry with the oldest `lastSeenMs` timestamp. That slot is overwritten with the new device, preserving memory determinism.

---

## 4. API Endpoints Enabled

### 4.1 `GET /api/devices`
Streams real-time observations of nearby wireless devices formatted in JSON:
```json
{
  "count": 3,
  "devices": [
    {
      "mac": "00:4B:12:EF:49:38",
      "frame_count": 842,
      "first_seen_ms": 1054,
      "last_seen_ms": 42100,
      "last_rssi_dbm": -58,
      "min_rssi_dbm": -64,
      "max_rssi_dbm": -55,
      "is_ap": false
    },
    {
      "mac": "24:6F:28:1A:2B:3C",
      "frame_count": 3120,
      "first_seen_ms": 1102,
      "last_seen_ms": 42080,
      "last_rssi_dbm": -48,
      "min_rssi_dbm": -52,
      "max_rssi_dbm": -46,
      "is_ap": true
    }
  ]
}
```

### 4.2 `GET /api/stats`
Updated to reflect `unique_observed_devices` and `malformed_frames_count`:
```json
{
  "monitoring_status": "ACTIVE",
  "active_channel": 11,
  "total_observed_frames": 14500,
  "current_frame_rate": 112.5,
  "unique_observed_devices": 7,
  "management_frame_count": 2840,
  "data_frame_count": 11660,
  "control_frame_count": 0,
  "dropped_frames_count": 0,
  "malformed_frames_count": 0
}
```

---

## 5. Verification & Testing

### 5.1 Host-Side Unit Tests
Run the independent Python unit test in the terminal:
```powershell
python tests/test_metadata_processing.py
```
Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.000s

OK
```
Tests cover:
- MAC address sanitization (rejects broadcast, multicast bit, and all zeros).
- 802.11 wire-length boundary checking (10 to 2,346 bytes).
- Deterministic LRU eviction behavior under capacity saturation.

### 5.2 Embedded Hardware Testing
1. Upload [`firmware/main/ForensiTap/ForensiTap.ino`](file:///d:/forensitap-ESP32/firmware/main/ForensiTap/ForensiTap.ino) in Arduino IDE 2.x.
2. In Serial Monitor, observe the `[Wi-Fi Monitor Subsystem: MON]` diagnostic report. It will list the number of unique devices tracked and display a sample of active MAC addresses with packet counts and signal strengths.
3. In your laptop browser or terminal, query `http://192.168.1.26/api/devices` to verify the JSON array of real wireless devices captured over Channel 11.
