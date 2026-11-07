# ForensiTap-ESP32: System Constraints & Architectural Limitations

## 1. Overview

An academically rigorous engineering project must clearly define its technical boundaries, hardware constraints, and threat model assumptions. The ForensiTap-ESP32 appliance is built upon low-cost, commodity edge hardware (ESP32-WROOM-32). While remarkably capable, the micro-controller's architecture introduces distinct physical and protocol limitations that distinguish it from enterprise-grade distributed network taps.

---

## 2. Physical & Hardware Constraints

### 2.1 Single 2.4 GHz Transceiver Limitation
- **Single-Radio Topology:** The ESP32 contains a single 2.4 GHz RF frontend shared between Wi-Fi and Bluetooth. It cannot monitor 5 GHz (802.11a/n/ac) or 6 GHz (802.11ax/be Wi-Fi 6E/7) spectrum.
- **Single-Channel Coexistence:** In connected mode (Station Mode providing HTTP REST server access), the physical radio frequency is locked to the primary channel of the associated Access Point (Channel 11 in our tests).
- **Channel Hopping Constraint:** While promiscuous mode supports frequency hopping across Channels 1–13, hopping necessarily breaks the TCP connection to the local network, interrupting live HTTP dashboard streaming. Multi-channel monitoring in connected mode would require dual-radio hardware (e.g., dual ESP32s or dedicated RF transceiver).

### 2.2 Microcontroller Memory Budget & Queue Depth
- **Queue Absorption Capacity:** The FreeRTOS packet queue is bounded at 64 entries to preserve dynamic RAM. While sufficient for typical background traffic ($50$ to $300\,\text{fps}$), an extreme volumetric denial-of-service flood ($> 5,000\,\text{fps}$) will saturate the queue, resulting in dropped frame counts (`dropped_frames_count`).
- **Ring Buffer Volatility:** The in-memory evidence chain holds 32 blocks in RAM ($\approx 8\,\text{KB}$). When new blocks are minted beyond 32, older blocks slide out of the in-memory window. While the cryptographic tip hash (`tip_hash`) permanently preserves chain continuity, raw historical blocks must be harvested by the laptop streaming collector (`collector.py`) to prevent loss.

### 2.3 Non-Volatile Flash Wear Considerations
- The ESP32's internal SPI flash memory supports approximately $100,000$ write/erase cycles per block. Writing every promiscuous frame or high-frequency telemetry snapshot directly to flash would cause premature silicon wear-out within days. Consequently, active frames and sliding windows reside purely in dynamic RAM, and evidence is streamed to external host storage.

---

## 3. Protocol & Cryptographic Boundaries

### 3.1 Metadata-Only Observation (Payload Opacity)
- **Encryption Boundaries:** In modern WPA2/WPA3 encrypted wireless networks, frame payloads are encrypted with AES-CCMP or GCMP. ForensiTap does not possess decryption keys and cannot inspect higher-layer TCP/UDP payloads or HTTP contents.
- **Observable Surface:** Analysis is strictly restricted to IEEE 802.11 physical and MAC layer header metadata: Frame Type/Subtype, Frame Length, Sequence Control, Transmitter MAC, Receiver MAC, BSSID, and RSSI signal strength.

### 3.2 802.11w Protected Management Frames (PMF)
- Under legacy 802.11 networks, Deauthentication and Disassociation frames are sent in plain text, making deauthentication floods trivially detectable.
- Under WPA3 and 802.11w PMF, management frames are cryptographically authenticated with a Management MIC. While ForensiTap can still observe the occurrence and frequency of management frames, it cannot distinguish between legitimately authenticated teardowns and forged attacks without the Pairwise Transient Key (PTK).

---

## 4. Operational Comparison Matrix

| Capability / Attribute | Enterprise Dedicated Sensor (e.g., Cisco/Aruba) | Laptop with Wireshark & Alfa Card | ForensiTap-ESP32 Appliance |
|---|---|---|---|
| **Cost** | $\$1,000 - \$5,000$ | $\$800 - \$1,500$ | **$<\$10$** |
| **Power Consumption** | $15 - 30\,\text{W}$ (PoE) | $45 - 90\,\text{W}$ | **$< 0.8\,\text{W}$ (USB-Powered)** |
| **Form Factor** | Rackmount / Large AP | Laptop + External USB Antennas | **Single Micro-controller Board** |
| **RF Spectrum** | 2.4 GHz, 5 GHz, 6 GHz Dual/Tri-Radio | 2.4 GHz & 5 GHz (adapter dependent) | **2.4 GHz Single-Band (Channels 1-14)** |
| **Packet Inspection** | Full Deep Packet Inspection (DPI) | Full Payload Capture (PCAP) | **Header Metadata & Flow Statistics** |
| **Evidence Protection** | Centralized Syslog / SIEM | Local PCAP / Filesystem | **Hardware SHA-256 Hash Chain** |
| **Physical Tamper Detection** | Optical / Micro-switch Chassis | Operating System Logs | **Dedicated Sensor ISR Interrupt** |
| **Deployment Footprint** | Enterprise Infrastructure | Heavy / Mobile Forensics | **Decentralized IoT Edge Sensor** |

---

## 5. Mitigation Strategies & Future Recommendations

1. **Dual-ESP32 Architecture:** A future revision can pair two ESP32 modules: Module A acts as a dedicated full-spectrum channel-hopping sniffer, streaming raw metadata over UART/SPI to Module B, which manages network connectivity, feature extraction, and hash chaining.
2. **External MicroSD / FRAM Module:** Integrating an SPI MicroSD card socket with wear-leveling or non-volatile ferroelectric RAM (FRAM) would allow persistent on-appliance storage of hundreds of thousands of evidence blocks without wear concerns.
3. **External 5 GHz Transceiver:** Adding a secondary low-cost 5 GHz receiver module would expand spectral coverage across modern enterprise bands.
