# ForensiTap-ESP32: What It Solves, How It Works, and What It Detects

**Academic Project Title:** ForensiTap-ESP32: A Low-Cost Wireless Network Monitoring, Anomaly Detection and Tamper-Evident Forensic Logging System  
**Hardware Platform:** DOIT ESP32 DevKit V1 (ESP32-WROOM-32 @ 240 MHz)  
**Host Workstation:** Windows Laptop with Python 3 Analytics & Web Dashboard  

---

## PART 1 — WHAT REAL-WORLD PROBLEM FORENSITAP ACTUALLY SOLVES

### 1.1 The Blind Spot in Wireless Network Security
In modern corporate, industrial, and smart-home IoT environments, wireless networks (IEEE 802.11) represent the most vulnerable perimeter:
- Radio waves propagate freely beyond physical walls, fences, and security checkpoints.
- Anyone within radio range can passively eavesdrop on frame metadata, inject rogue frames, jam channels, or attempt unauthorized association without leaving a trace on traditional wired firewall logs.

### 1.2 Why Existing Commercial Solutions Fail for Distributed IoT
Traditional approaches to wireless intrusion detection (WIDS) and network forensics suffer from three fatal flaws:
1. **Prohibitive Cost:** Commercial enterprise wireless sensors (such as Cisco CleanAir or Aruba AirWave) cost between **\$1,000 and \$5,000 per access point**. Deploying them across dozens of branch offices, smart agriculture fields, warehouses, or campus facilities is economically impossible for small/medium enterprises and academic institutions.
2. **High Power & Heavy Hardware:** Laptop-based solutions (using an external Alfa Wi-Fi USB adapter running Kali Linux and Wireshark) consume **45 to 90 Watts**, cost upwards of \$1,000, and cannot be left unattended in a ceiling crawlspace or remote enclosure.
3. **The "Chain of Custody" Forensic Trust Problem:** Conventional syslog servers and flat log files (`.log` or `.pcap`) are stored in plain text. A rogue administrator, an attacker who gains root access, or a compromised IoT gateway can easily edit, truncate, or delete log entries to conceal an intrusion. In court or during a certified forensic audit, plain text logs lack mathematical proof of immutability.

### 1.3 What ForensiTap-ESP32 Actually Solves
ForensiTap-ESP32 completely re-engineers this paradigm:
- **$<\$10$ Appliance:** Achieves real-time 802.11 wireless monitoring, edge anomaly detection, and forensic logging using a commodity ESP32 microcontroller costing under \$10.
- **Ultra-Low Power Footprint:** Consumes less than **0.8 Watts** ($< 160\,\text{mA}$ @ 5V DC via micro-USB or battery), allowing continuous 24/7 autonomous deployment in air vents, ceilings, or remote enclosures.
- **Tamper-Evident Cryptographic Chain of Custody:** Every single boot event, network state change, and detected anomaly is cryptographically sealed into an append-only **SHA-256 hash chain** directly on the microcontroller. Any post-capture alteration of a single byte, bit, or timestamp immediately breaks the mathematical hash chain and is flagged during audit.
- **Dual-Mode Coexistence:** Solves the classic embedded trade-off by running the 802.11 promiscuous frame capture engine simultaneously alongside an active Wi-Fi Station connection and REST HTTP WebServer on a single 2.4 GHz radio.

---

## PART 2 — HOW THE ACTUAL SYSTEM WORKS (END-TO-END FLOW)

The operation of ForensiTap-ESP32 spans six synchronized layers from raw radio waves to browser visualization:

```mermaid
flowchart TD
    subgraph Layer 1: Physical Radio Ingress
        RF[802.11 b/g/n Radio Waves (Channel 11)] --> PROMIS[Promiscuous Sniffer Filter]
        PROMIS --> ISR[IRAM_ATTR Sub-Microsecond Callback]
        ISR --> QUEUE[FreeRTOS Bounded Frame Queue (64 slots)]
    end

    subgraph Layer 2: Metadata Processing & Entity Tracking
        QUEUE --> PARSER[802.11 Frame Header Parser]
        PARSER --> SANITIZE[MAC Sanitizer: Filter Broadcast & Multicast]
        SANITIZE --> LRU[32-Slot LRU Device Tracking Table]
    end

    subgraph Layer 3: Edge Statistical Feature Engine
        PARSER --> BUCKETS[10-Second Sliding Window: 10 x 1s Buckets]
        BUCKETS --> WELFORD[Welford Online Mean & Variance Algorithm]
        WELFORD --> VECTOR[7-Dimensional Feature Vector: FPS, Bytes, Mgmt%, Burst, Z-Score]
    end

    subgraph Layer 4: Deterministic Anomaly Detection
        VECTOR --> RULES[5 Deterministic Security Rules]
        LRU --> RULES
        RULES --> COOLDOWN[30-Second Deduplication & Cooldown Filter]
        COOLDOWN --> ALERTRING[16-Slot FIFO Alert Ring Buffer]
    end

    subgraph Layer 5: Cryptographic Forensic Logging
        ALERTRING --> CANONICAL[Canonical Pipe-Delimited Serializer]
        CANONICAL --> SHA256[Hardware mbedTLS SHA-256 Engine]
        SHA256 --> CHAIN[Immutable Hash Chain: PrevHash + CurrentHash]
    end

    subgraph Layer 6: Egress & Analytics
        CHAIN --> REST[WebServer Port 80: 7 REST JSON Endpoints]
        REST --> DASH[Cybersecurity Web Dashboard: Chart.js Live UI]
        REST --> COLLECTOR[Python Streaming Collector: Multi-Stream JSONL]
        COLLECTOR --> ANALYTICS[Offline Forensic Traffic Analytics Engine]
        COLLECTOR --> ML[Host-Side Machine Learning Anomaly Scorer]
    end
```

### Step 1: Physical Radio Capture (Layer 1)
1. The ESP32 Wi-Fi hardware is configured in promiscuous mode on Channel 11 (`WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA`).
2. When an 802.11 packet hits the antenna, an interrupt fires within $< 1\,\mu\text{s}$, executing `wifiPromiscuousRxCallback()` located in ultra-fast `IRAM_ATTR` memory.
3. The raw frame header is copied into a statically allocated FreeRTOS queue (`xQueueSendFromISR`) without blocking the radio core.

### Step 2: Metadata Extraction & Device Tracking (Layer 2)
1. The non-blocking main loop dequeues frames and parses the IEEE 802.11 Frame Control field.
2. Identifies frame types:
   - **Management Frames:** Beacons (Type 0, Subtype 8), Probe Requests (Subtype 4), Deauthentications (Subtype 12), Disassociations (Subtype 10).
   - **Data Frames:** Unencrypted and Encrypted Wi-Fi payload frames.
3. **MAC Address Sanitization:** Extracts Transmitter Address (TA), Receiver Address (RA), and BSSID. Discards invalid broadcast (`FF:FF:FF:FF:FF:FF`), multicast (`01:00:5E:...`), and null addresses.
4. **LRU Device Table:** Updates an active table of up to 32 observed devices. Records total packets, role (AP vs Station), last-seen timestamp, and RSSI signal strength. If the table is full, the least-recently-seen device is evicted.

### Step 3: Statistical Feature Extraction (Layer 3)
1. Rather than storing millions of raw packets, ForensiTap compresses stream traffic into a **10-second sliding window** partitioned into 10 discrete 1-second circular buckets.
2. Every second, the oldest bucket expires and a new bucket opens, continuously computing:
   - Observed frame rate (FPS).
   - Byte throughput (bytes/second).
   - Average frame size (bytes).
   - Active unique peers.
   - Management frame ratio (Management frames / Total frames).
   - Traffic burstiness score ($\text{Peak 1s bucket} / \text{Average 1s bucket}$).
3. **Adaptive Baseline Learning (Welford's Algorithm):** Continuously updates the running mean ($\mu$) and standard deviation ($\sigma$) of the channel's frame rate in $O(1)$ time without keeping an array of historical samples. Calculates the real-time $Z$-score deviation:
   $$Z = \frac{\text{Current FPS} - \mu}{\sigma}$$

### Step 4: Rule-Based Edge Anomaly Detection (Layer 4)
1. Every second, the anomaly detector evaluates 5 deterministic mathematical rules.
2. If a rule condition is met, an alert is generated.
3. To prevent log storms and serial flooding during sustained denial-of-service attacks, independent 30-second cooldown timers suppress repetitive duplicate alerts.
4. Alerts are stored in a circular FIFO ring buffer of 16 slots in static RAM.

### Step 5: Cryptographic Evidence Sealing (Layer 5)
1. Whenever a boot event, network transition, or security alert is raised, it is forwarded to the Evidence Logger.
2. The block is formatted into a canonical pipe-delimited string:
   $$\text{Canonical Payload} = \text{index} \parallel "|" \parallel \text{timestamp\_ms} \parallel "|" \parallel \text{event\_type} \parallel "|" \parallel \text{severity} \parallel "|" \parallel \text{description} \parallel "|" \parallel \text{prev\_hash}$$
3. The ESP32's hardware cryptographic accelerator computes $\text{SHA-256}(\text{Canonical})$ in $< 25\,\mu\text{s}$.
4. Block #0 (Genesis Block) uses a predefined `prev_hash` of 64 zeros. Every subsequent block #N embeds the exact 64-character hash of block #N-1, forming an immutable hash chain.

### Step 6: Telemetry Egress, Live Dashboard & Analytics (Layer 6)
1. The built-in WebServer exposes 7 REST API endpoints on port 80:
   - `GET /api/health`: Uptime, free heap, Wi-Fi channel, RSSI.
   - `GET /api/stats`: Aggregate frame totals, frame rates, dropped packet count.
   - `GET /api/features`: 10-second sliding window statistics and baseline Z-scores.
   - `GET /api/devices`: Streaming JSON list of all tracked MAC addresses.
   - `GET /api/alerts`: List of detected security anomalies.
   - `GET /api/logs`: Full cryptographic evidence chain.
   - `GET /api/logs/verify`: On-chip cryptographic self-audit recalculating all SHA-256 hashes.
   - `GET /api/export?format=csv`: Downloadable CSV evidence ledger.
2. The browser dashboard (`dashboard/index.html`) plots live traffic in Chart.js, updates device tables, and provides a one-click "Audit Chain Now" button.
3. The laptop collector (`laptop/collector/collector.py`) archives sessions into structured JSONL files.
4. The offline analytics engine (`laptop/analytics/traffic_analysis.py`) and host-side ML model (`laptop/ml/train.py` & `inference.py`) score complex behavioral shifts.

---

## PART 3 — WHAT FORENSITAP ACTUALLY DETECTS (ATTACK & ANOMALY CATALOG)

ForensiTap-ESP32 features dual-tier detection: **Tier 1 (Deterministic On-Chip Edge Rules)** and **Tier 2 (Host-Side Unsupervised Machine Learning)**.

| Anomaly / Attack Type | Detection Mechanism | Trigger Condition | Severity | Threat Explained & Real-World Impact |
|---|---|---|---|---|
| **1. Deauthentication & Disassociation Flood** | Tier 1 (Rule 2) + Tier 2 (ML) | `mgmtFrameRatio >= 0.60` (60%) AND `windowFrameCount >= 20` | `WARNING` / `HIGH` | **Wi-Fi Denial-of-Service / WPA Handshake Theft:** An attacker transmits spoofed deauth frames to kick legitimate devices off the network. Common in Evil Twin and WPA2 handshake capture attacks (e.g. using `aireplay-ng` or Flipper Zero). |
| **2. Abrupt Traffic Spike & Exfiltration** | Tier 1 (Rule 1) + Tier 2 (ML) | $Z = \frac{\text{FPS} - \mu}{\sigma} \ge +3.0$ AND $\text{FPS} > 20$ | `MEDIUM` / `WARNING` | **Volumetric Flooding / High-Volume Data Exfiltration:** Detects sudden bursts of transmission exceeding 3 standard deviations from normal ambient baseline (e.g., active network scanning, large file theft over Wi-Fi, or brute-force packet injection). |
| **3. Rogue AP & Unauthorized Station Probing** | Tier 1 (Rule 3) | New unique MAC inserted into device table (`notifyNewDevice`) | `INFO` | **Evil Twin / Rogue Base Station:** Discovers unknown access points broadcasting beacons or unauthorized client devices probing for saved SSIDs. Logs MAC, AP/STA role, and RSSI signal strength. |
| **4. Traffic Micro-Bursts & Pulse Jamming** | Tier 1 (Rule 4) + Tier 2 (ML) | $\text{burstScore} = \frac{\text{Peak 1s}}{\text{Avg 1s}} \ge 5.0$ | `WARNING` | **Pulsed Jamming & Periodic Beacon Stuffing:** Detects stealthy short-duration micro-bursts where average traffic appears normal, but single-second bursts exceed 5 times the window mean. |
| **5. Appliance Saturation & Buffer Overflow** | Tier 1 (Rule 5) | `droppedFramesCount > lastDropped` | `ERROR` | **Monitoring System Health Defense:** Detects when ambient wireless traffic exceeds the 64-slot queue capacity, alerting the forensic investigator that CPU saturation or channel flooding has caused frame drops. |
| **6. Cryptographic Evidence Tampering** | Cryptographic Hash Chain | Block Hash $\neq$ $\text{SHA-256}(\text{Canonical})$ OR $\text{prev\_hash}_i \neq \text{block\_hash}_{i-1}$ | `CRITICAL` | **Post-Capture Evidence Manipulation:** Detects if an attacker, compromised host, or corrupted storage medium attempts to alter an observed MAC address, delete a log line, or modify a timestamp in the evidence ledger. |
| **7. Multi-Dimensional Behavioral Anomalies** | Tier 2 (Host ML Model) | Robust Mahalanobis Distance $D(\mathbf{x}) \ge \tau$ (Sigmoid Prob $> 50\%$) | `ANOMALY` | **Complex Correlated Attacks:** Detects stealthy attacks where individual metrics stay below hard thresholds, but multi-dimensional deviations (e.g. elevated burstiness combined with dropped average frame size and high peer churn) indicate malicious activity. |

---

## PART 4 — EMPIRICAL HARDWARE PROOF & VALIDATION SUMMARY

During live hardware evaluation on Channel 11, the system achieved the following verified milestones:
1. **Total Frames Captured:** Over **115,000 frames** ingested continuously without crash or reboot.
2. **Device Tracking:** 32 unique wireless devices (7 Access Points, 25 client stations) simultaneously tracked in LRU memory.
3. **Live Anomaly Triggers:**
   - Real-world traffic spikes detected live: **208.1 fps ($Z = +3.43$)** and **266.3 fps ($Z = +3.03$)**.
   - 22+ alerts generated and cryptographically sealed into the SHA-256 chain.
4. **Cryptographic Immutability:** On-chip `/api/logs/verify` and host-side `verify_logs.py` confirmed 100% hash continuity across all blocks from Genesis to tip.
5. **Memory & Concurrency Stability:**
   - Free dynamic heap maintained above **208,000 bytes** ($> 63\%$ available).
   - Multi-threaded stress testing: **70 concurrent burst requests served at 11.9 requests/sec with 100% success rate and zero memory leaks**.
