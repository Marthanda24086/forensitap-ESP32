/**
 * @file ForensiTap.ino
 * @brief ForensiTap-ESP32 Main Firmware Entry Point (Stage 11 Anomaly Detector)
 *
 * Project: ForensiTap-ESP32
 * Academic Title: A Low-Cost Wireless Network Monitoring, Anomaly Detection
 *                 and Tamper-Evident Forensic Logging System.
 *
 * Stage 11 Focus:
 * - Deterministic statistical anomaly detection engine (ForensiTapDetector).
 * - Rule 1: Traffic spike (Z-score deviation).
 * - Rule 2: Management frame anomaly (ratio threshold).
 * - Rule 3: New device observation alert (informational).
 * - Rule 4: Activity deviation (burstiness score).
 * - Rule 5: Monitoring health (queue saturation).
 * - Alert deduplication and configurable cooldowns.
 * - Integration with REST API (/api/alerts).
 */

#include <Arduino.h>
#include "system_config.h"
#include "events.h"
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "network_manager.h"
#include "wifi_monitor.h"
#include "feature_engine.h"
#include "detector.h"
#include "evidence_logger.h"
#include "api_server.h"

// =============================================================================
// SYSTEM RUNTIME INSTANCES & TIMING
// =============================================================================
static SystemConfig g_config;
static SystemState  g_state;

// Monotonic task timing timestamps (unsigned long for rollover safety)
static unsigned long g_lastHeartbeatMillis = 0;
static unsigned long g_lastStatusMillis = 0;

// Maximum registered modular subsystems
static const size_t MAX_MODULES = 8;
static IModule* g_modules[MAX_MODULES];
static size_t   g_moduleCount = 0;

// =============================================================================
// SUBSYSTEM REGISTRATION & MANAGEMENT
// =============================================================================

/**
 * @brief Registers a subsystem implementing IModule with the core dispatcher.
 * @param module Pointer to the subsystem instance.
 * @return true if successfully registered, false if capacity exceeded.
 */
bool registerModule(IModule* module) {
    if (!module || g_moduleCount >= MAX_MODULES) {
        LOG_ERROR("SYS", "Failed to register module: slot unavailable or null pointer");
        return false;
    }
    g_modules[g_moduleCount++] = module;
    LOG_INFO("SYS", "Registered module: [%s]", module->getName());
    return true;
}

// =============================================================================
// SYSTEM INITIALIZATION PHASES
// =============================================================================

/**
 * @brief Phase 1: Hardware Abstraction & Serial Interface Setup
 */
void initHardware() {
    DiagnosticLogger::init(g_config.serialBaud);
    DiagnosticLogger::printStartupBanner(g_config);
    LOG_INFO("SYS", "Phase 1: Hardware abstraction initialized at %lu bps", g_config.serialBaud);
}

/**
 * @brief Phase 2: Memory & Silicon Baseline Diagnostics
 */
void checkSystemBaseline() {
    g_state.freeHeapBytes = ESP.getFreeHeap();
    LOG_INFO("SYS", "Phase 2: Baseline heap evaluation: %u bytes available", g_state.freeHeapBytes);

    if (g_state.freeHeapBytes < 100000) {
        LOG_WARN("SYS", "Low baseline heap detected! Remaining: %u bytes", g_state.freeHeapBytes);
        g_state.isHealthy = false;
    } else {
        LOG_INFO("SYS", "Memory budget verification: NOMINAL");
    }
}

/**
 * @brief Phase 3: Modular Subsystem Initialization
 */
void initSubsystems() {
    LOG_INFO("SYS", "Phase 3: Initializing %u registered subsystems...", g_moduleCount);

    for (size_t i = 0; i < g_moduleCount; ++i) {
        if (g_modules[i]) {
            LOG_INFO("SYS", "Initializing subsystem [%s]...", g_modules[i]->getName());
            bool success = g_modules[i]->init(g_config);
            if (!success) {
                LOG_ERROR("SYS", "Subsystem [%s] initialization FAILED!", g_modules[i]->getName());
                g_state.isHealthy = false;
            } else {
                LOG_INFO("SYS", "Subsystem [%s] initialization SUCCESS", g_modules[i]->getName());
            }
        }
    }
}

/**
 * @brief Phase 4: System State Transition & Boot Event Generation
 */
void finalizeBootSequence() {
    g_state.bootTimestampMs = millis();
    g_state.currentMode = g_config.operationalMode;

    // Create and dispatch boot confirmation event
    SystemEvent bootEvent;
    bootEvent.eventId = ++g_state.totalEventsLogged;
    bootEvent.timestampMs = g_state.bootTimestampMs;
    bootEvent.type = EventType::SYSTEM_BOOT;
    bootEvent.severity = EventSeverity::SEV_INFO;
    strncpy(bootEvent.source, "SYS", sizeof(bootEvent.source) - 1);
    bootEvent.source[sizeof(bootEvent.source) - 1] = '\0';
    snprintf(bootEvent.description, sizeof(bootEvent.description),
             "ForensiTap v%s initialized in mode %u",
             FORENSITAP_VERSION_STR, static_cast<uint8_t>(g_state.currentMode));

    DiagnosticLogger::logEvent(bootEvent);
    g_evidenceLogger.logEvidence("SYSTEM_BOOT", "INFO", bootEvent.description);
    LOG_INFO("SYS", "Phase 4: Boot sequence completed in %lu ms. Dispatcher running.", g_state.bootTimestampMs);
}

// =============================================================================
// ARDUINO LIFECYCLE: SETUP
// =============================================================================

void setup() {
    // Instantiate default configuration and initial telemetry state
    g_config = SystemConfig::createDefault();
    g_config.defaultWifiChannel = 11; // Configured to user's verified AP channel
    g_state  = SystemState::createInitial();

    // Register active modular subsystems in dependency order
    registerModule(&g_networkManager);
    registerModule(&g_wifiMonitor);
    registerModule(&g_featureEngine);
    registerModule(&g_detector);
    registerModule(&g_evidenceLogger);
    registerModule(&g_apiServer);

    // Execute sequential initialization pipeline
    initHardware();
    checkSystemBaseline();
    initSubsystems();
    finalizeBootSequence();
}

// =============================================================================
// ARDUINO LIFECYCLE: LOOP (NON-BLOCKING TASK DISPATCHER)
// =============================================================================

void loop() {
    unsigned long currentMillis = millis();

    // -------------------------------------------------------------------------
    // Task 1: Periodic Liveness Heartbeat (every 2000 ms)
    // -------------------------------------------------------------------------
    if (currentMillis - g_lastHeartbeatMillis >= g_config.heartbeatIntervalMs) {
        g_lastHeartbeatMillis = currentMillis;

        // Dynamic status check on network, monitor, and API server
        const char* netStatus = g_networkManager.isConnected() ? "WIFI_CONNECTED" : "WIFI_OFFLINE";
        const char* apiStatus = g_apiServer.isRunning() ? "API_ACTIVE" : "API_STANDBY";
        const char* monStatus = g_wifiMonitor.isMonitoring() ? "MON_ACTIVE" : "MON_STANDBY";

        const FeatureVector& feat = g_featureEngine.getLatestFeatures();

        LOG_INFO("LIV", "[HEARTBEAT] ForensiTap | %s | %s | %s | %.0f fps | %u peers | Alerts: %u | Blocks: %u | Uptime: %lu s | Heap: %u B",
                 netStatus, monStatus, apiStatus,
                 feat.frameRate, feat.uniquePeers,
                 g_detector.getAlertCount(),
                 g_evidenceLogger.getStoredBlockCount(),
                 currentMillis / 1000, ESP.getFreeHeap());
    }

    // -------------------------------------------------------------------------
    // Task 1b: Machine-Readable Telemetry Stream for Dashboard (every 1000 ms)
    // -------------------------------------------------------------------------
    static unsigned long g_lastTelemetryMillis = 0;
    if (currentMillis - g_lastTelemetryMillis >= 1000) {
        g_lastTelemetryMillis = currentMillis;

        const FeatureVector& feat = g_featureEngine.getLatestFeatures();
        float throughputKbps = (feat.byteRate * 8.0f) / 1000.0f;
        bool isWifiConnected = g_networkManager.isConnected();
        String ipStr = isWifiConnected ? g_networkManager.getLocalIP().toString() : "0.0.0.0";

        Serial.printf("@FEATURES {\"frame_rate\":%.1f,\"throughput_kbps\":%.1f,\"byte_rate\":%.1f,\"deauth_rate\":%.1f,\"disassoc_rate\":%.1f,\"deauth_ratio\":%.3f,\"burst_score\":%.2f,\"mgmt_ratio\":%.3f,\"unique_peers\":%u,\"uptime_sec\":%lu,\"alerts_total\":%u,\"wifi_connected\":%s,\"ip_address\":\"%s\"}\n",
            feat.frameRate,
            throughputKbps,
            feat.byteRate,
            feat.deauthRate,
            feat.disassocRate,
            feat.deauthRatio,
            feat.burstScore,
            feat.managementRatio,
            feat.uniquePeers,
            currentMillis / 1000,
            g_detector.getAlertCount(),
            isWifiConnected ? "true" : "false",
            ipStr.c_str());
    }

    // -------------------------------------------------------------------------
    // Task 2: Subsystem Periodic Execution Slices (Non-blocking)
    // -------------------------------------------------------------------------
    for (size_t i = 0; i < g_moduleCount; ++i) {
        if (g_modules[i]) {
            g_modules[i]->update(currentMillis);
        }
    }

    // Update global state metrics from active monitor
    g_state.totalFramesObserved = g_wifiMonitor.getTotalFrames();
    g_state.droppedFramesCount = g_wifiMonitor.getDroppedFrames();

    // Dynamic operating mode tracking
    if (g_networkManager.isConnected()) {
        g_state.currentMode = OperatingMode::MODE_CONNECTED;
    } else {
        g_state.currentMode = OperatingMode::MODE_STANDALONE;
    }

    // -------------------------------------------------------------------------
    // Task 3: Comprehensive Telemetry & Subsystem Diagnostics (every 10000 ms)
    // -------------------------------------------------------------------------
    if (currentMillis - g_lastStatusMillis >= g_config.statusIntervalMs) {
        g_lastStatusMillis = currentMillis;

        g_state.freeHeapBytes = ESP.getFreeHeap();
        DiagnosticLogger::printSystemStatus(g_state);

        // Query diagnostic report from registered subsystems
        for (size_t i = 0; i < g_moduleCount; ++i) {
            if (g_modules[i]) {
                g_modules[i]->printDiagnostics();
            }
        }
    }
}
