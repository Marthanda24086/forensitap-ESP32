#ifndef FEATURE_ENGINE_H
#define FEATURE_ENGINE_H

#include <Arduino.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "system_config.h"

/**
 * @file feature_engine.h
 * @brief Sliding-window statistical feature extraction, granular subtype analysis, and adaptive baseline engine.
 *
 * ForensiTap-ESP32 Appliance
 */

#define FEATURE_WINDOW_BUCKETS 10 // 10 buckets of 1 second = 10-second sliding window
#define BASELINE_WARMUP_WINDOWS 6 // 6 windows x 10s = 60s warm-up period

/**
 * @brief One-second time bucket accumulating raw window counts and 802.11 subtypes.
 */
struct WindowBucket {
    uint32_t frameCount;
    uint32_t byteCount;
    uint32_t mgmtCount;
    uint32_t dataCount;
    uint32_t ctrlCount;
    uint32_t deauthCount;   ///< Subtype 0x0C (Deauthentication)
    uint32_t disassocCount; ///< Subtype 0x0A (Disassociation)
    uint32_t beaconCount;   ///< Subtype 0x08 (Beacon)
    uint32_t probeReqCount; ///< Subtype 0x04 (Probe Request)
};

/**
 * @brief Extracted statistical feature vector across 10-second window.
 */
struct FeatureVector {
    uint16_t windowDurationSec;
    float    frameRate;             ///< Frames per second across 10s window
    float    byteRate;              ///< Bytes per second across 10s window
    float    avgFrameSize;          ///< Average frame size in bytes
    uint16_t uniquePeers;           ///< Number of active MAC addresses in window
    float    managementRatio;       ///< Ratio of management frames (0.0 to 1.0)
    float    burstScore;            ///< Peak 1s rate / Average 10s rate (>= 1.0)

    // Granular Subtype metrics
    float    deauthRate;            ///< Deauth frames per second in window
    float    disassocRate;          ///< Disassoc frames per second in window
    float    deauthRatio;           ///< Ratio of (deauth + disassoc) to total frames
    float    beaconRate;            ///< Beacon frames per second

    // Baseline statistics
    bool     baselineReady;         ///< True if warm-up period is complete
    float    baselineMeanRate;      ///< Long-term running mean frame rate (Welford)
    float    baselineStdDevRate;    ///< Standard deviation of frame rate
    float    rateDeviationZScore;   ///< Instantaneous Z-score deviation from baseline
    float    baselineEwmaMean;      ///< Adaptive Exponentially Weighted Moving Average baseline
};

class ForensiTapFeatureEngine : public IModule {
public:
    ForensiTapFeatureEngine();
    virtual ~ForensiTapFeatureEngine() {}

    // IModule Lifecycle Interface
    virtual const char* getName() const override { return "FEAT"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // Frame Ingestion Feed (called by WifiMonitor with optional subtype)
    void recordFrame(uint16_t length, uint8_t frameType, uint8_t frameSubtype = 0);

    // Feature Retrieval
    const FeatureVector& getLatestFeatures() const;

private:
    void rotateBucket();
    void computeWindowFeatures();
    void updateBaseline(float currentRate);

    // Circular 1-second sub-buckets
    WindowBucket m_buckets[FEATURE_WINDOW_BUCKETS];
    uint8_t      m_currentBucketIdx;
    unsigned long m_lastBucketRotateMillis;

    // Active Feature Vector
    FeatureVector m_features;

    // Baseline Tracking State (Welford's algorithm + Adaptive EWMA)
    uint32_t m_baselineWindowCount;
    float    m_baselineM;           // Running mean
    float    m_baselineS;           // Running M2 (for variance)
    float    m_baselineEwma;        // Running adaptive EWMA
};

extern ForensiTapFeatureEngine g_featureEngine;

#endif // FEATURE_ENGINE_H
