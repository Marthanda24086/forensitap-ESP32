#ifndef SYSTEM_CONFIG_H
#define SYSTEM_CONFIG_H

#include <Arduino.h>

/**
 * @file system_config.h
 * @brief Central system configuration, versioning, and operational definitions.
 *
 * ForensiTap-ESP32 Appliance
 */

// =============================================================================
// FIRMWARE VERSION METADATA
// =============================================================================
#define FORENSITAP_VERSION_MAJOR 1
#define FORENSITAP_VERSION_MINOR 0
#define FORENSITAP_VERSION_PATCH 0
#define FORENSITAP_VERSION_TAG   "stage5-arch"
#define FORENSITAP_VERSION_STR   "1.0.0-stage5-arch"
#define FORENSITAP_TARGET_HW     "ESP32 DevKit V1 (ESP32-WROOM-32)"

// =============================================================================
// HARDWARE & COMMUNICATION PARAMETERS
// =============================================================================
#define SERIAL_DEFAULT_BAUD      115200
#define SERIAL_BOOT_SETTLE_MS    1000

// Non-blocking task intervals (milliseconds)
#define DEFAULT_HEARTBEAT_MS     2000
#define DEFAULT_STATUS_REPORT_MS 10000

// Feature engine & queue bounds (applied in subsequent stages)
#define DEFAULT_FEATURE_WINDOW_SEC 10
#define MAX_OBSERVATION_QUEUE_LEN  64
#define MAX_DEVICE_TABLE_ENTRIES   32
#define MAX_ALERT_HISTORY_COUNT    16
#define MAX_FORENSIC_CHAIN_RECORDS 32

// =============================================================================
// OPERATING MODES & STATE ENUMERATIONS
// =============================================================================
enum class OperatingMode : uint8_t {
    MODE_BOOT = 0,               ///< Initial power-on and self-test
    MODE_STANDALONE = 1,         ///< Serial-only diagnostics, no active RF transmission
    MODE_CONNECTED = 2,          ///< Station mode: connected to AP for HTTP API & Dashboard
    MODE_PROMISCUOUS = 3,        ///< 802.11 monitor mode: passive raw frame ingestion
    MODE_ERROR = 4               ///< Degraded state upon peripheral or memory fault
};

/**
 * @brief Centralized system configuration structure.
 * Avoids dispersed preprocessor flags and global configuration clutter.
 */
struct SystemConfig {
    uint32_t serialBaud;
    uint32_t heartbeatIntervalMs;
    uint32_t statusIntervalMs;
    OperatingMode operationalMode;
    uint16_t featureWindowSec;
    uint16_t observationQueueCapacity;
    uint8_t defaultWifiChannel;

    // Default configuration factory
    static SystemConfig createDefault() {
        SystemConfig cfg;
        cfg.serialBaud = SERIAL_DEFAULT_BAUD;
        cfg.heartbeatIntervalMs = DEFAULT_HEARTBEAT_MS;
        cfg.statusIntervalMs = DEFAULT_STATUS_REPORT_MS;
        cfg.operationalMode = OperatingMode::MODE_STANDALONE;
        cfg.featureWindowSec = DEFAULT_FEATURE_WINDOW_SEC;
        cfg.observationQueueCapacity = MAX_OBSERVATION_QUEUE_LEN;
        cfg.defaultWifiChannel = 1;
        return cfg;
    }
};

/**
 * @brief System runtime telemetry state structure.
 */
struct SystemState {
    OperatingMode currentMode;
    uint32_t bootTimestampMs;
    uint32_t totalEventsLogged;
    uint32_t totalFramesObserved;
    uint32_t droppedFramesCount;
    uint32_t freeHeapBytes;
    bool isHealthy;

    static SystemState createInitial() {
        SystemState st;
        st.currentMode = OperatingMode::MODE_BOOT;
        st.bootTimestampMs = 0;
        st.totalEventsLogged = 0;
        st.totalFramesObserved = 0;
        st.droppedFramesCount = 0;
        st.freeHeapBytes = 0;
        st.isHealthy = true;
        return st;
    }
};

#endif // SYSTEM_CONFIG_H
