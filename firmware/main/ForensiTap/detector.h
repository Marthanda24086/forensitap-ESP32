#ifndef DETECTOR_H
#define DETECTOR_H

#include <Arduino.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "system_config.h"
#include "events.h"
#include "feature_engine.h"

/**
 * @file detector.h
 * @brief Rule-based deterministic anomaly detection engine.
 *
 * ForensiTap-ESP32 Appliance
 */

#define MAX_STORED_ALERTS 16

/**
 * @brief Structured anomaly alert record.
 */
struct SecurityAlert {
    uint32_t      eventId;
    uint32_t      timestampMs;
    EventType     type;
    EventSeverity severity;
    char          description[96];
};

/**
 * @brief Configurable threshold parameters for deterministic detection rules.
 */
struct DetectorThresholds {
    float    spikeZScore;          ///< Z-score threshold for traffic spikes (default: 3.0)
    float    mgmtRatioThreshold;   ///< Threshold for management frame ratio (default: 0.60 = 60%)
    float    burstScoreThreshold;  ///< Threshold for burstiness score (default: 5.0)
    uint32_t alertCooldownMs;      ///< Minimum time between recurring rule alerts (default: 30000 ms)

    static DetectorThresholds createDefault() {
        DetectorThresholds t;
        t.spikeZScore = 3.0f;
        t.mgmtRatioThreshold = 0.60f;
        t.burstScoreThreshold = 5.0f;
        t.alertCooldownMs = 30000;
        return t;
    }
};

class ForensiTapDetector : public IModule {
public:
    ForensiTapDetector();
    virtual ~ForensiTapDetector() {}

    // IModule Lifecycle Interface
    virtual const char* getName() const override { return "DET"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // External Event Ingestion
    void notifyNewDevice(const char* macStr, bool isAp, int8_t rssi);

    // Alert Buffer Retrieval
    uint16_t getAlertCount() const { return m_alertCount; }
    const SecurityAlert* getAlerts() const { return m_alerts; }
    uint16_t getMaxAlertCapacity() const { return MAX_STORED_ALERTS; }

    // Threshold Configuration
    void setThresholds(const DetectorThresholds& thresholds) { m_thresholds = thresholds; }
    const DetectorThresholds& getThresholds() const { return m_thresholds; }

private:
    void evaluateRules(unsigned long currentMillis);
    void raiseAlert(EventType type, EventSeverity severity, const char* description);

    // Rule Evaluation Routines
    void checkRule1TrafficSpike(const FeatureVector& feat, unsigned long currentMillis);
    void checkRule2ManagementAnomaly(const FeatureVector& feat, unsigned long currentMillis);
    void checkRule4ActivityBurst(const FeatureVector& feat, unsigned long currentMillis);
    void checkRule5MonitoringHealth(unsigned long currentMillis);

    DetectorThresholds m_thresholds;

    // Circular Alert Ring Buffer
    SecurityAlert m_alerts[MAX_STORED_ALERTS];
    uint16_t      m_alertCount;
    uint32_t      m_totalAlertsGenerated;

    // Cooldown Timestamps (prevents alert storms)
    unsigned long m_lastTrafficSpikeMs;
    unsigned long m_lastMgmtAnomalyMs;
    unsigned long m_lastBurstAlertMs;
    unsigned long m_lastHealthAlertMs;
    uint32_t      m_lastObservedDroppedCount;
    unsigned long m_lastRuleEvalMillis;
};

extern ForensiTapDetector g_detector;

#endif // DETECTOR_H
