# Stage 10: Statistical Feature Extraction Engine

## 1. Overview

**Stage 10** implements the embedded real-time feature extraction and statistical baseline engine: **`ForensiTapFeatureEngine`** (`firmware/feature_engine/feature_engine.cpp` and `feature_engine.h`).

The engine aggregates high-throughput frame observations over a **10-second sliding time window**, computing 6 key statistical metrics without machine learning and without dynamic heap allocation. It maintains an adaptive statistical baseline using **Welford's algorithm** to quantify ambient network normality.

---

## 2. Sliding-Window Architecture

```
Time --->
[ Bucket 0 ] [ Bucket 1 ] [ Bucket 2 ] ... [ Bucket 9 ]
  (1 sec)      (1 sec)      (1 sec)          (1 sec)
|<------------------- 10-Second Sliding Window ------------------->|
```

- **Circular Ring of 10 Sub-Buckets:** Every second, the engine advances `m_currentBucketIdx` and clears the oldest 1-second slot.
- **Microsecond Ingestion:** Each incoming frame from `ForensiTapWifiMonitor` increments the current sub-bucket's frame counter, byte counter, and type counters (`mgmt`, `data`, `ctrl`) in $O(1)$ time.
- **Zero Heap Footprint:** The entire sliding window occupies less than **250 bytes** of static memory.

---

## 3. Mathematical Feature Definitions

### 3.1 `frame_rate` (fps)
$$\text{frame\_rate} = \frac{\sum_{i=0}^{9} \text{frameCount}_i}{\text{window\_duration}}$$
- **Window duration:** $10.0$ seconds.
- Quantifies instantaneous channel density.

### 3.2 `byte_rate` (Bytes/sec)
$$\text{byte\_rate} = \frac{\sum_{i=0}^{9} \text{byteCount}_i}{\text{window\_duration}}$$
- Measures physical wire bandwidth utilization.

### 3.3 `average_frame_size` (Bytes)
$$\text{average\_frame\_size} = \begin{cases} \frac{\sum \text{byteCount}}{\sum \text{frameCount}} & \text{if } \sum \text{frameCount} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$
- Distinguishes small control/probe frames (~60–120 B) from heavy data payloads (~1500 B).

### 3.4 `unique_peers`
$$\text{unique\_peers} = \text{Unique Unicast MACs active in window}$$
- Sourced directly from `ForensiTapWifiMonitor::getUniqueDeviceCount()`.

### 3.5 `management_frame_ratio`
$$\text{management\_frame\_ratio} = \begin{cases} \frac{\sum \text{mgmtCount}}{\sum \text{frameCount}} & \text{if } \sum \text{frameCount} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$
- Normalized value between $0.0$ and $1.0$. Under normal conditions, management traffic typically accounts for $10\%$ to $25\%$ of frames. Spikes above $50\%$ suggest probing, beacon flood, or deauthentication attacks.

### 3.6 `traffic_burst_score`
$$\text{traffic\_burst\_score} = \begin{cases} \frac{\max_{i} (\text{frameCount}_i)}{\text{average\_bucket\_frames}} & \text{if } \text{average\_bucket\_frames} > 0 \\ 1.0 & \text{otherwise} \end{cases}$$
- **Interpretation:**
  - $\approx 1.0$: Uniform traffic distribution across the 10 seconds.
  - $> 3.0$: Burst traffic pattern (a burst occurring in a single 1-second interval).

---

## 4. Adaptive Baseline Profiling (Welford's Algorithm)

To detect anomalies in Stage 11 without storing large historical arrays, the engine tracks the long-term running mean ($\mu$) and standard deviation ($\sigma$) using Welford's algorithm:

For each completed 10-second window $k$:
$$M_k = M_{k-1} + \frac{x_k - M_{k-1}}{k}$$
$$S_k = S_{k-1} + (x_k - M_{k-1})(x_k - M_k)$$
$$\sigma_k = \sqrt{\frac{S_k}{k - 1}}$$

### 4.1 Warm-Up Period
- **Threshold:** 6 consecutive windows (60 seconds) are required before `baselineReady = true`.
- Prevents premature false alerts during system startup.

### 4.2 Z-Score Deviation
$$Z = \frac{\text{frame\_rate} - \mu}{\sigma}$$
Quantifies how many standard deviations current traffic diverges from historical normality.

---

## 5. REST API Integration (`GET /api/features`)

Query `http://192.168.1.26/api/features`:
```json
{
  "window_duration_sec": 10,
  "frame_rate": 154.20,
  "byte_rate": 78240.00,
  "average_frame_size": 507.39,
  "unique_peers": 15,
  "management_frame_ratio": 0.185,
  "traffic_burst_score": 1.28,
  "baseline": {
    "warmup_ready": true,
    "mean_frame_rate": 146.50,
    "std_frame_rate": 12.30,
    "frame_rate_zscore": 0.63
  }
}
```

---

## 6. Verification

1. **Python Unit Tests:**
   ```powershell
   python tests/test_feature_engine.py
   ```
   Validates mathematical formulas, zero-denominator safeguards, and Welford variance calculation against Python standard library `statistics`.
2. **Compilation Verification:**
   Verified with `arduino-cli compile` for `DOIT ESP32 DEVKIT V1` with exit code 0.
