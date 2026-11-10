# Project Analysis: ForensiTap-ESP32
**Autonomous Premium Digital Product Development — Phase 1 Discovery**

---

## 1. Executive Summary & Product Identity
**ForensiTap-ESP32** is a sub-\$10 dedicated hardware security appliance that continuously captures 802.11 Wi-Fi frames in promiscuous monitor mode, analyzes Layer 2 wireless traffic patterns in real-time using online statistical algorithms (Welford's algorithm + Adaptive EWMA) and an embedded Edge Decision Tree Classifier, and seals every detected cyber incident into an immutable, court-admissible SHA-256 cryptographic evidence hash chain.

* **Target Audience:** Cyber defense engineers, SOC incident responders, forensic investigators, corporate network administrators, security researchers, and academic evaluators.
* **Core Value Proposition:** 
  1. *Eliminates Cost Barrier:* Replaces \$2,000–\$5,000 enterprise WIDS sensors with a \$5–\$10 passive hardware node.
  2. *Layer 2 Visibility:* Exposes stealth attacks (deauthentication floods, association hijacking, rogue evil twin APs) invisible to standard IP firewalls and endpoint security agents.
  3. *Cryptographic Evidence Integrity:* Solves syslog mutability by anchoring incidents in an unbroken SHA-256 hash chain from Genesis Anchor to Tip.

---

## 2. Technical Architecture & Subsystems
```
┌────────────────────────────────────────────────────────────────────────┐
│                        FORENSITAP-ESP32 ARCHITECTURE                   │
├──────────────────────────┬─────────────────────────────────────────────┤
│ Core 0 (PRO_CPU)         │ Core 1 (APP_CPU)                            │
│  - Promiscuous RX ISR    │  - Statistical Feature Engine (Welford/EWMA)│
│  - FreeRTOS Ring Queue   │  - Deterministic Rule Detector & Edge ML    │
│  - Low-level PHY driver  │  - Cryptographic Evidence Logger (SHA-256)  │
│                          │  - Embedded HTTP REST & WebSerial API       │
└──────────────────────────┴─────────────────────────────────────────────┘
```

### Key Firmware & Backend Components:
* `wifi_monitor`: Promiscuous packet callback with 64-element FreeRTOS queue and 32-slot LRU device tracking table.
* `feature_engine`: 10-second rolling aggregation across 1-second sub-buckets; computes FPS, byte rate, management ratio, burst score, and granular subtype counters (deauth `0x0C`, disassoc `0x0A`, beacon `0x08`).
* `detector`: 7-rule deterministic engine + embedded Edge Decision Tree Classifier (`edge_ml_classifier.h`).
* `evidence_logger`: MbedTLS SHA-256 hash chain with Genesis anchor, tip tracking, and continuous mathematical integrity auditing.
* `api_server`: Embedded REST server exposing `/api/health`, `/api/stats`, `/api/features`, `/api/devices`, `/api/alerts`, `/api/logs`, `/api/logs/verify`, and `/api/export`.

---

## 3. Current Design Weaknesses
1. **Information Overload:** Prior interface presented raw mathematical symbols (e.g. `+3.42σ`, `LRU Eviction`, `0.82 ratio`) without contextual plain-English root causes or recommended responses.
2. **Lack of Visual Hierarchy:** The hero banner, radar, charts, and tables competed for visual attention at equal visual weight.
3. **Generic Aesthetic Trap:** Relied on plain dark cards without sophisticated editorial structure, subtle depth, high-precision typography, or cohesive design tokens.
4. **Desktop-Only Spacing:** Tightly packed columns created horizontal overflow and compromised readability on mobile and tablet devices.
5. **Static Data Visualization:** Missing dynamic interactive canvas animations for the 2.4 GHz airspace radar and cryptographic chain exploration.

---

## 4. Current Technical Weaknesses
1. **Lack of In-Browser Hardware Connectivity:** Required manual local IP entry without direct USB fallback for air-gapped forensic investigations.
2. **Missing Granular Subtype Metrics:** Previous versions lacked direct deauth/disassoc frame rate displays on the primary dashboard.
3. **Single Monolithic View:** Users had to scroll endlessly through overview text, architecture charts, and live operational consoles simultaneously.

---

## 5. Proposed Digital Product Direction
To transform this into an award-winning, agency-grade digital product:
1. **Dual-Mode Architectural Navigation:** 
   - *Public Product & Technical Showcase:* Clean editorial hero, visual hardware specifications, interactive threat models, and court admissibility proof.
   - *SOC Tactical Cockpit:* Distraction-free, high-density cyber operations console with real-time telemetry, 2.4 GHz polar airspace radar, and explainable incident cards.
2. **Airspace Constellation Radar:** Bespoke HTML5 Canvas 2D polar radar with smooth continuous sweeping beam, concentric RSSI rings ($-30$ to $-90\text{ dBm}$), and interactive device inspection.
3. **Interactive Visual Blockchain Explorer:** Visual connected node graph with cryptographic verification indicators and an interactive "Simulate 1-Byte Corruption" sandbox demonstrating tamper-evidence.
4. **WebSerial API:** Native plug-and-play browser USB connection for Chrome, Edge, and Opera.
5. **Design System & Typography:** Obsidian base (`#070a12`), cyan telemetry accents (`#06b6d4`), emerald verification (`#10b981`), amber warnings (`#f59e0b`), crimson alerts (`#ef4444`), paired with `Inter` and `JetBrains Mono`.

---

## 6. Implementation Roadmap
* **Phase 2:** Design research on top-tier design references (Awwwards, Godly, Land-book, Refero).
* **Phase 3:** Complete design system specifications (`DESIGN_SYSTEM.md`).
* **Phase 4–6:** Frontend architecture & premium website implementation.
* **Phase 7–10:** Advanced motion design, responsive scaling (1920px to 375px), accessibility (ARIA/WCAG), and performance optimization.
* **Phase 11–13:** Automated browser visual inspection & iterative refinement rounds with headless Chrome.
* **Phase 14:** Complete documentation and delivery artifacts.
