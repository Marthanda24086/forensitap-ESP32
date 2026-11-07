#include "detector.h"
#include "wifi_monitor.h"
#include "evidence_logger.h"

// Global singleton instance
ForensiTapDetector g_detector;

ForensiTapDetector::ForensiTapDetector()
    : m_alertCount(0),
      m_totalAlertsGenerated(0),
      m_lastTrafficSpikeMs(0),
      m_lastMgmtAnomalyMs(0),
      m_lastBurstAlertMs(0),
      m_lastHealthAlertMs(0),
      m_lastObservedDroppedCount(0),
      m_lastRuleEvalMillis(0) {
    m_thresholds = DetectorThresholds::createDefault();
    memset(m_alerts, 0, sizeof(m_alerts));
}

bool ForensiTapDetector::init(const SystemConfig& config) {
    LOG_INFO("DET", "Initializing Deterministic Anomaly Detector subsystem...");
    m_alertCount = 0;
    m_totalAlertsGenerated = 0;
    m_lastRuleEvalMillis = millis();
    return true;
}

void ForensiTapDetector::raiseAlert(EventType type, EventSeverity severity, const char* description) {
    if (!description) return;

    size_t slot = 0;
    if (m_alertCount < MAX_STORED_ALERTS) {
        slot = m_alertCount++;
    } else {
        // Shift oldest alert out to maintain chronological FIFO buffer
        for (size_t i = 0; i < MAX_STORED_ALERTS - 1; ++i) {
            m_alerts[i] = m_alerts[i + 1];
        }
        slot = MAX_STORED_ALERTS - 1;
    }

    m_alerts[slot].eventId = ++m_totalAlertsGenerated;
    m_alerts[slot].timestampMs = millis();
    m_alerts[slot].type = type;
    m_alerts[slot].severity = severity;
    strncpy(m_alerts[slot].description, description, sizeof(m_alerts[slot].description) - 1);
    m_alerts[slot].description[sizeof(m_alerts[slot].description) - 1] = '\0';

    // Log structured alert to console
    SystemEvent evt;
    evt.eventId = m_alerts[slot].eventId;
    evt.timestampMs = m_alerts[slot].timestampMs;
    evt.type = type;
    evt.severity = severity;
    strncpy(evt.source, "DET", sizeof(evt.source) - 1);
    evt.source[sizeof(evt.source) - 1] = '\0';
    strncpy(evt.description, description, sizeof(evt.description) - 1);
    evt.description[sizeof(evt.description) - 1] = '\0';
    DiagnosticLogger::logEvent(evt);

    // Cryptographically seal alert into tamper-evident hash chain
    g_evidenceLogger.logEvidence(eventTypeToString(type), eventSeverityToString(severity), description);
}

void ForensiTapDetector::notifyNewDevice(const char* macStr, bool isAp, int8_t rssi) {
    if (!macStr) return;
    char buf[96];
    snprintf(buf, sizeof(buf), "New device observed: [%s] (%s, RSSI: %d dBm)",
             macStr, isAp ? "AP" : "STA", rssi);
    raiseAlert(EventType::NEW_DEVICE_OBSERVED, EventSeverity::SEV_INFO, buf);
}

void ForensiTapDetector::checkRule1TrafficSpike(const FeatureVector& feat, unsigned long currentMillis) {
    if (!feat.baselineReady) return;

    // Trigger if Z-score exceeds configured threshold (e.g. +3.0 std deviations)
    if (feat.rateDeviationZScore >= m_thresholds.spikeZScore) {
        if (currentMillis - m_lastTrafficSpikeMs >= m_thresholds.alertCooldownMs) {
            m_lastTrafficSpikeMs = currentMillis;

            char buf[96];
            snprintf(buf, sizeof(buf), "Traffic spike detected: %.1f fps (Z-Score: +%.2f > +%.1f)",
                     feat.frameRate, feat.rateDeviationZScore, m_thresholds.spikeZScore);
            raiseAlert(EventType::TRAFFIC_SPIKE, EventSeverity::SEV_MEDIUM, buf);
        }
    }
}

void ForensiTapDetector::checkRule2ManagementAnomaly(const FeatureVector& feat, unsigned long currentMillis) {
    // Only evaluate if traffic density is non-trivial (> 5 fps)
    if (feat.frameRate > 5.0f && feat.managementRatio >= m_thresholds.mgmtRatioThreshold) {
        if (currentMillis - m_lastMgmtAnomalyMs >= m_thresholds.alertCooldownMs) {
            m_lastMgmtAnomalyMs = currentMillis;

            char buf[96];
            snprintf(buf, sizeof(buf), "Management ratio anomaly: %.1f%% mgmt frames (threshold: %.0f%%)",
                     feat.managementRatio * 100.0f, m_thresholds.mgmtRatioThreshold * 100.0f);
            raiseAlert(EventType::MGMT_ANOMALY, EventSeverity::SEV_HIGH, buf);
        }
    }
}

void ForensiTapDetector::checkRule4ActivityBurst(const FeatureVector& feat, unsigned long currentMillis) {
    // Detect sudden packet pulses where 1-second density heavily dominates the 10s window
    if (feat.frameRate > 10.0f && feat.burstScore >= m_thresholds.burstScoreThreshold) {
        if (currentMillis - m_lastBurstAlertMs >= m_thresholds.alertCooldownMs) {
            m_lastBurstAlertMs = currentMillis;

            char buf[96];
            snprintf(buf, sizeof(buf), "High traffic burstiness: score %.2f (threshold: %.1f)",
                     feat.burstScore, m_thresholds.burstScoreThreshold);
            raiseAlert(EventType::ACTIVITY_DEVIATION, EventSeverity::SEV_LOW, buf);
        }
    }
}

void ForensiTapDetector::checkRule5MonitoringHealth(unsigned long currentMillis) {
    uint32_t currentDropped = g_wifiMonitor.getDroppedFrames();

    if (currentDropped > m_lastObservedDroppedCount + 10) {
        if (currentMillis - m_lastHealthAlertMs >= m_thresholds.alertCooldownMs) {
            m_lastHealthAlertMs = currentMillis;

            char buf[96];
            snprintf(buf, sizeof(buf), "Observation queue saturated: %u frames dropped",
                     currentDropped - m_lastObservedDroppedCount);
            raiseAlert(EventType::MONITOR_HEALTH_ALERT, EventSeverity::SEV_HIGH, buf);
        }
    }
    m_lastObservedDroppedCount = currentDropped;
}

void ForensiTapDetector::evaluateRules(unsigned long currentMillis) {
    const FeatureVector& feat = g_featureEngine.getLatestFeatures();

    checkRule1TrafficSpike(feat, currentMillis);
    checkRule2ManagementAnomaly(feat, currentMillis);
    checkRule4ActivityBurst(feat, currentMillis);
    checkRule5MonitoringHealth(currentMillis);
}

void ForensiTapDetector::update(unsigned long currentMillis) {
    // Evaluate deterministic rules once per second
    if (currentMillis - m_lastRuleEvalMillis >= 1000) {
        m_lastRuleEvalMillis = currentMillis;
        evaluateRules(currentMillis);
    }
}

bool ForensiTapDetector::isHealthy() const {
    return true;
}

void ForensiTapDetector::printDiagnostics() {
    Serial.println("  +-- [Anomaly Detector Subsystem: DET]");
    Serial.printf("  |   Rules Active    : TrafficSpike, MgmtAnomaly, NewDevice, Burst, Health\n");
    Serial.printf("  |   Total Alerts    : %u raised | Buffer: %u / %u stored\n",
                  m_totalAlertsGenerated, m_alertCount, MAX_STORED_ALERTS);
    if (m_alertCount > 0) {
        const SecurityAlert& last = m_alerts[m_alertCount - 1];
        Serial.printf("  |   Latest Alert    : [#%u][%s] %s\n",
                      last.eventId, eventSeverityToString(last.severity), last.description);
    }
    Serial.println("  +------------------------------------");
}
