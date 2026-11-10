# ForensiTap-ESP32 Design System
**Autonomous Premium Digital Product Development — Phase 3 Specification**

---

## 1. Visual Identity & Design Philosophy
The ForensiTap-ESP32 visual system embodies **Tactile Cyber-Physical Intelligence**:
* **High-Precision Engineering:** Built for cybersecurity professionals and forensic evaluators who demand technical rigor over superficial decoration.
* **Explainable Telemetry:** Translates complex statistical math (Welford Z-scores, EWMA baselines, LRU device caches) into human-digestible visual insights.
* **Cryptographic Transparency:** Makes mathematical immutability tangible through interactive blockchain explorers and real-time tamper simulations.

---

## 2. Color System & Design Tokens

```
Token                Hex Code       Role / Application
-----------------------------------------------------------------------------
--bg-dark            #070a12        Deep obsidian canvas background
--bg-surface         #0c1220        Top header & secondary surface elevation
--bg-card            #111a2e        Primary component & card container
--bg-card-hover      #18233d        Hover state for interactive cards
--border-color       #1e2c48        Structural 1px component borders
--border-accent      #2a3d66        Focused or highlighted element borders

--text-primary       #f8fafc        Primary headings, high-contrast values
--text-secondary     #94a3b8        Body copy, descriptive explanations
--text-muted         #64748b        Captions, timestamps, secondary labels

--cyan-primary       #06b6d4        Primary telemetry accent, radio channels, AP nodes
--cyan-glow          rgba(6,182,212,0.25)
--green-success      #10b981        Verified cryptographic state, client STA nodes
--green-glow         rgba(16,185,129,0.25)
--amber-warning      #f59e0b        Burst alerts, elevated baseline warnings
--amber-glow         rgba(245,158,11,0.25)
--red-danger         #ef4444        Deauth attacks, rogue APs, cryptographic tampering
--red-glow           rgba(239,68,68,0.28)
--purple-accent      #8b5cf6        Adaptive EWMA baseline curve, USB serial state
--purple-glow        rgba(139,92,246,0.25)
```

---

## 3. Typography Hierarchy

### Font Families
* **Primary Sans-Serif:** `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
* **Telemetry Monospace:** `JetBrains Mono`, "Fira Code", Consolas, monospace

### Scale & Hierarchy
| Style | Size | Weight | Line Height | Tracking | Application |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Display 1** | 2.1rem (33.6px) | 800 (ExtraBold) | 1.2 | -0.02em | Hero headline |
| **Heading 2** | 1.7rem (27.2px) | 700 (Bold) | 1.3 | -0.01em | Section titles, View headers |
| **Heading 3** | 1.15rem (18.4px)| 700 (Bold) | 1.4 | -0.01em | Brand title, KPI labels |
| **Card Title**| 0.88rem (14px)  | 600 (SemiBold) | 1.4 | 0 | Card headers, table headers |
| **Body Text** | 0.82rem (13.1px)| 400/500 (Regular)| 1.5 | 0 | Narrative explanations, descriptions |
| **Mono Metric**| 1.6rem (25.6px)| 700 (Bold) | 1.2 | 0 | Large numerical KPI figures |
| **Mono Data** | 0.75rem (12px)  | 500 (Medium) | 1.4 | 0 | MAC addresses, hashes, rates |
| **Micro Caption**| 0.68rem (10.8px)| 600 (SemiBold) | 1.2 | +0.06em | Category tags, timestamps |

---

## 4. Spacing, Elevation & Grids
* **Base Unit:** 4px scale (`0.25rem = 4px`, `0.5rem = 8px`, `0.75rem = 12px`, `1rem = 16px`, `1.5rem = 24px`, `2rem = 32px`).
* **Container Max Width:** `1480px` centered with fluid responsive padding (`1.5rem` desktop, `0.75rem` mobile).
* **Tactical Split Grid:** 
  - Desktop ($>1100\text{px}$): 1.45fr (Telemetry, Radar, Devices) / 1.0fr (Explainable Incidents, Feature Vector, Edge ML).
  - Tablet/Mobile ($\le 1100\text{px}$): Single-column stack with persistent tab navigation.

---

## 5. Core Reusable Component Tokens

### 1. KPI Metric Card
```css
.kpi-card {
    background: #111a2e;
    border: 1px solid #1e2c48;
    border-radius: 10px;
    padding: 1rem 1.15rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 100%; height: 3px;
    background: var(--accent);
}
```

### 2. Explainable Incident Card
```css
.incident-card {
    background: #0e1526;
    border: 1px solid #1e2c48;
    border-left: 4px solid var(--severity-color);
    border-radius: 8px;
    padding: 0.85rem 1rem;
}
```

### 3. Airspace Polar Radar
```css
#airspaceRadarCanvas {
    background: #090f1d;
    border-radius: 50%;
    border: 1px solid #2a3d66;
    box-shadow: 0 0 24px rgba(6, 182, 212, 0.12), inset 0 0 24px rgba(0, 0, 0, 0.6);
}
```

### 4. Cryptographic Blockchain Node
```css
.chain-block-node {
    background: #111a2e;
    border: 1px solid #1e2c48;
    border-radius: 8px;
    padding: 0.75rem 0.85rem;
    min-width: 160px;
}
.chain-block-node.valid { border-top: 3px solid #10b981; }
.chain-block-node.corrupted { border-top: 3px solid #ef4444; background: rgba(239, 68, 68, 0.1); }
```
