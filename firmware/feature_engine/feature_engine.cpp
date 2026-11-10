#include "feature_engine.h"
#include "wifi_monitor.h"
#include <math.h>

// Global singleton instance
ForensiTapFeatureEngine g_featureEngine;

ForensiTapFeatureEngine::ForensiTapFeatureEngine()
    : m_currentBucketIdx(0),
      m_lastBucketRotateMillis(0),
      m_baselineWindowCount(0),
      m_baselineM(0.0f),
      m_baselineS(0.0f),
      m_baselineEwma(0.0f) {
    memset(m_buckets, 0, sizeof(m_buckets));
    memset(&m_features, 0, sizeof(m_features));
    m_features.windowDurationSec = FEATURE_WINDOW_BUCKETS;
    m_features.burstScore = 1.0f;
}

bool ForensiTapFeatureEngine::init(const SystemConfig& config) {
    LOG_INFO("FEAT", "Initializing Statistical Feature Extraction Engine (Window: %u s, EWMA Active)...", 
             FEATURE_WINDOW_BUCKETS);
    memset(m_buckets, 0, sizeof(m_buckets));
    m_currentBucketIdx = 0;
    m_lastBucketRotateMillis = millis();
    m_baselineWindowCount = 0;
    m_baselineM = 0.0f;
    m_baselineS = 0.0f;
    m_baselineEwma = 0.0f;
    m_features.baselineReady = false;
    return true;
}

void ForensiTapFeatureEngine::recordFrame(uint16_t length, uint8_t frameType, uint8_t frameSubtype) {
    // Accumulate into active 1-second time bucket
    m_buckets[m_currentBucketIdx].frameCount++;
    m_buckets[m_currentBucketIdx].byteCount += length;

    switch (frameType) {
        case 0: // Management Frame
            m_buckets[m_currentBucketIdx].mgmtCount++;
            if (frameSubtype == 0x0C) {
                m_buckets[m_currentBucketIdx].deauthCount++;
            } else if (frameSubtype == 0x0A) {
                m_buckets[m_currentBucketIdx].disassocCount++;
            } else if (frameSubtype == 0x08) {
                m_buckets[m_currentBucketIdx].beaconCount++;
            } else if (frameSubtype == 0x04) {
                m_buckets[m_currentBucketIdx].probeReqCount++;
            }
            break;
        case 1: // Control Frame
            m_buckets[m_currentBucketIdx].ctrlCount++;
            break;
        case 2: // Data Frame
            m_buckets[m_currentBucketIdx].dataCount++;
            break;
        default:
            break;
    }
}

void ForensiTapFeatureEngine::rotateBucket() {
    // Move to next 1-second slot in circular array
    m_currentBucketIdx = (m_currentBucketIdx + 1) % FEATURE_WINDOW_BUCKETS;
    // Clear the oldest slot to start fresh for the next second
    memset(&m_buckets[m_currentBucketIdx], 0, sizeof(WindowBucket));
}

void ForensiTapFeatureEngine::computeWindowFeatures() {
    uint32_t totalFrames = 0;
    uint32_t totalBytes = 0;
    uint32_t totalMgmt = 0;
    uint32_t totalDeauth = 0;
    uint32_t totalDisassoc = 0;
    uint32_t totalBeacons = 0;
    uint32_t maxBucketFrames = 0;

    // Aggregate across all 10 discrete 1-second sub-buckets
    for (size_t i = 0; i < FEATURE_WINDOW_BUCKETS; ++i) {
        totalFrames   += m_buckets[i].frameCount;
        totalBytes    += m_buckets[i].byteCount;
        totalMgmt     += m_buckets[i].mgmtCount;
        totalDeauth   += m_buckets[i].deauthCount;
        totalDisassoc += m_buckets[i].disassocCount;
        totalBeacons  += m_buckets[i].beaconCount;

        if (m_buckets[i].frameCount > maxBucketFrames) {
            maxBucketFrames = m_buckets[i].frameCount;
        }
    }

    // 1. Frame Rate (frames / sec across 10s)
    m_features.frameRate = (float)totalFrames / (float)FEATURE_WINDOW_BUCKETS;

    // 2. Byte Rate (bytes / sec across 10s)
    m_features.byteRate = (float)totalBytes / (float)FEATURE_WINDOW_BUCKETS;

    // 3. Average Frame Size (bytes / frame, zero-protected)
    m_features.avgFrameSize = (totalFrames > 0) ? ((float)totalBytes / (float)totalFrames) : 0.0f;

    // 4. Unique Peers (from active device table)
    m_features.uniquePeers = g_wifiMonitor.getUniqueDeviceCount();

    // 5. Management Frame Ratio (mgmt / total, zero-protected)
    m_features.managementRatio = (totalFrames > 0) ? ((float)totalMgmt / (float)totalFrames) : 0.0f;

    // 6. Traffic Burst Score: Peak 1-second frame count divided by the window average
    float avgBucketFrames = (float)totalFrames / (float)FEATURE_WINDOW_BUCKETS;
    if (avgBucketFrames > 0.0f) {
        m_features.burstScore = (float)maxBucketFrames / avgBucketFrames;
    } else {
        m_features.burstScore = 1.0f;
    }

    // 7. Granular Subtype Rates & Ratios
    m_features.deauthRate = (float)totalDeauth / (float)FEATURE_WINDOW_BUCKETS;
    m_features.disassocRate = (float)totalDisassoc / (float)FEATURE_WINDOW_BUCKETS;
    m_features.beaconRate = (float)totalBeacons / (float)FEATURE_WINDOW_BUCKETS;
    m_features.deauthRatio = (totalFrames > 0) ? ((float)(totalDeauth + totalDisassoc) / (float)totalFrames) : 0.0f;

    // 8. Baseline Statistics Update (evaluated once per 10-second window)
    updateBaseline(m_features.frameRate);
}

void ForensiTapFeatureEngine::updateBaseline(float currentRate) {
    m_baselineWindowCount++;

    // Welford's algorithm for numerically stable running mean and sample variance
    if (m_baselineWindowCount == 1) {
        m_baselineM = currentRate;
        m_baselineS = 0.0f;
        m_baselineEwma = currentRate;
    } else {
        float oldM = m_baselineM;
        m_baselineM += (currentRate - oldM) / (float)m_baselineWindowCount;
        m_baselineS += (currentRate - oldM) * (currentRate - m_baselineM);

        // Adaptive EWMA baseline (alpha = 0.05, responds smoothly to day/night shifts)
        const float alpha = 0.05f;
        m_baselineEwma = (alpha * currentRate) + ((1.0f - alpha) * m_baselineEwma);
    }

    m_features.baselineMeanRate = m_baselineM;
    m_features.baselineEwmaMean = m_baselineEwma;

    // Variance & Standard Deviation
    if (m_baselineWindowCount > 1) {
        float variance = m_baselineS / (float)(m_baselineWindowCount - 1);
        m_features.baselineStdDevRate = sqrtf(variance);
    } else {
        m_features.baselineStdDevRate = 0.0f;
    }

    // Check if warm-up period is complete (e.g. 6 windows = 60s)
    if (m_baselineWindowCount >= BASELINE_WARMUP_WINDOWS) {
        m_features.baselineReady = true;

        // Compute Z-score deviation against EWMA / standard deviation
        if (m_features.baselineStdDevRate > 0.1f) {
            m_features.rateDeviationZScore = (currentRate - m_features.baselineEwmaMean) / m_features.baselineStdDevRate;
        } else {
            m_features.rateDeviationZScore = 0.0f;
        }
    } else {
        m_features.baselineReady = false;
        m_features.rateDeviationZScore = 0.0f;
    }
}

void ForensiTapFeatureEngine::update(unsigned long currentMillis) {
    // Advance 1-second time bucket and recompute 10-second rolling features
    if (currentMillis - m_lastBucketRotateMillis >= 1000) {
        rotateBucket();
        computeWindowFeatures();
        m_lastBucketRotateMillis = currentMillis;
    }
}

const FeatureVector& ForensiTapFeatureEngine::getLatestFeatures() const {
    return m_features;
}

bool ForensiTapFeatureEngine::isHealthy() const {
    return true;
}

void ForensiTapFeatureEngine::printDiagnostics() {
    Serial.println("  +-- [Feature Engine Subsystem: FEAT]");
    Serial.printf("  |   10s Window Rates: %.1f fps | %.1f KB/s | Deauth: %.1f fps\n", 
                  m_features.frameRate, m_features.byteRate / 1024.0f, m_features.deauthRate);
    Serial.printf("  |   Avg Frame Size  : %.1f bytes | Mgmt Ratio: %.2f (Deauth: %.1f%%)\n",
                  m_features.avgFrameSize, m_features.managementRatio, m_features.deauthRatio * 100.0f);
    Serial.printf("  |   Unique Peers    : %u devices | Burst Score: %.2f\n",
                  m_features.uniquePeers, m_features.burstScore);
    Serial.printf("  |   Baseline Status : %s (Windows: %u)\n",
                  m_features.baselineReady ? "READY (WARMED UP)" : "WARMING UP",
                  m_baselineWindowCount);
    if (m_features.baselineReady) {
        Serial.printf("  |   Baseline Profile: Welford: %.1f fps | EWMA: %.1f fps | Z-Score: %+.2f\n",
                      m_features.baselineMeanRate, m_features.baselineEwmaMean, m_features.rateDeviationZScore);
    }
    Serial.println("  +------------------------------------");
}
