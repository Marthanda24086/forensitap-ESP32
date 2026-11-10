#ifndef EVENTS_H
#define EVENTS_H

#include <Arduino.h>

/**
 * @file events.h
 * @brief Standardized event taxonomy and memory-bounded event structures.
 *
 * ForensiTap-ESP32 Appliance
 */

// =============================================================================
// EVENT ENUMERATIONS
// =============================================================================
enum class EventType : uint8_t {
    SYSTEM_BOOT = 0,             ///< Hardware power-on reset or warm restart
    HEARTBEAT,                  ///< Periodic system liveness indicator
    WIFI_STATE_CHANGE,          ///< Wi-Fi connection, disconnection, or mode toggle
    TRAFFIC_SPIKE,              ///< Abrupt surge in observed 802.11 frame rate
    MGMT_ANOMALY,               ///< Unusual ratio of deauth/disassoc or beacon bursts
    NEW_DEVICE_OBSERVED,        ///< First observation of an unseen MAC address (Informational)
    ACTIVITY_DEVIATION,         ///< Significant behavioral departure from baseline profile
    MONITOR_HEALTH_ALERT,       ///< Frame buffer saturation, dropped packets, or sniffer fault
    DEAUTH_FLOOD_ATTACK,        ///< Active 802.11 Deauth/Disassoc flood detected
    EVIL_TWIN_SUSPECTED,        ///< Suspected Rogue AP / BSSID spoofing via RSSI or duplicate beacon
    TAMPER_ALERT,               ///< Physical enclosure breach or magnetic field interruption
    STORAGE_WARNING,            ///< Non-volatile flash wear or storage budget exhaustion
    SYSTEM_ERROR                ///< Critical hardware or software runtime failure
};

enum class EventSeverity : uint8_t {
    SEV_INFO = 0,               ///< Normal diagnostic and informational messages
    SEV_LOW,                    ///< Minor deviations or low-priority telemetry
    SEV_MEDIUM,                 ///< Noteworthy statistical anomalies requiring audit
    SEV_HIGH,                   ///< Probable wireless attack or severe performance disruption
    SEV_CRITICAL                ///< Physical tampering, hardware failure, or storage exhaustion
};

// =============================================================================
// STANDARDIZED EVENT RECORD
// =============================================================================
struct SystemEvent {
    uint32_t eventId;           ///< Monotonically increasing event sequence identifier
    uint32_t timestampMs;       ///< Microcontroller uptime in milliseconds when event occurred
    EventType type;             ///< Specific category of the detected event
    EventSeverity severity;     ///< Assigned operational threat/urgency level
    char source[16];            ///< Originating subsystem tag (e.g., "SYS", "WIFI", "DET")
    char description[80];       ///< Human-readable, null-terminated summary string

    /**
     * @brief Formats event into a clean canonical string for console or serial transmission.
     * @param dest Target char buffer (must be at least 140 bytes).
     * @param maxLen Maximum writable size of dest buffer.
     */
    void toFormattedString(char* dest, size_t maxLen) const;
};

// =============================================================================
// HELPER CONVERSIONS
// =============================================================================
inline const char* eventTypeToString(EventType type) {
    switch (type) {
        case EventType::SYSTEM_BOOT:          return "SYSTEM_BOOT";
        case EventType::HEARTBEAT:            return "HEARTBEAT";
        case EventType::WIFI_STATE_CHANGE:    return "WIFI_STATE_CHANGE";
        case EventType::TRAFFIC_SPIKE:        return "TRAFFIC_SPIKE";
        case EventType::MGMT_ANOMALY:         return "MGMT_ANOMALY";
        case EventType::NEW_DEVICE_OBSERVED:  return "NEW_DEVICE_OBSERVED";
        case EventType::ACTIVITY_DEVIATION:   return "ACTIVITY_DEVIATION";
        case EventType::MONITOR_HEALTH_ALERT: return "MONITOR_HEALTH_ALERT";
        case EventType::DEAUTH_FLOOD_ATTACK:  return "DEAUTH_FLOOD_ATTACK";
        case EventType::EVIL_TWIN_SUSPECTED:  return "EVIL_TWIN_SUSPECTED";
        case EventType::TAMPER_ALERT:         return "TAMPER_ALERT";
        case EventType::STORAGE_WARNING:      return "STORAGE_WARNING";
        case EventType::SYSTEM_ERROR:         return "SYSTEM_ERROR";
        default:                              return "UNKNOWN_EVENT";
    }
}

inline const char* eventSeverityToString(EventSeverity severity) {
    switch (severity) {
        case EventSeverity::SEV_INFO:     return "INFO";
        case EventSeverity::SEV_LOW:      return "LOW";
        case EventSeverity::SEV_MEDIUM:   return "MEDIUM";
        case EventSeverity::SEV_HIGH:     return "HIGH";
        case EventSeverity::SEV_CRITICAL: return "CRITICAL";
        default:                          return "UNKNOWN";
    }
}

inline void SystemEvent::toFormattedString(char* dest, size_t maxLen) const {
    if (!dest || maxLen == 0) return;
    snprintf(dest, maxLen, "[#%05u][%10u ms][%s][%s][%s] %s",
             eventId,
             timestampMs,
             eventSeverityToString(severity),
             source,
             eventTypeToString(type),
             description);
}

#endif // EVENTS_H
