#include "diagnostic_logger.h"
#include <stdarg.h>

LogLevel DiagnosticLogger::s_minLevel = LogLevel::LOG_LVL_DEBUG;

void DiagnosticLogger::init(uint32_t baudRate) {
    Serial.begin(baudRate);
    // Allow hardware bridge and terminal buffers to stabilize
    delay(SERIAL_BOOT_SETTLE_MS);
}

void DiagnosticLogger::setLogLevel(LogLevel level) {
    s_minLevel = level;
}

LogLevel DiagnosticLogger::getLogLevel() {
    return s_minLevel;
}

const char* DiagnosticLogger::levelToString(LogLevel level) {
    switch (level) {
        case LogLevel::LOG_LVL_DEBUG: return "DEBUG";
        case LogLevel::LOG_LVL_INFO:  return "INFO ";
        case LogLevel::LOG_LVL_WARN:  return "WARN ";
        case LogLevel::LOG_LVL_ERROR: return "ERROR";
        default:                      return "UNKNOWN";
    }
}

void DiagnosticLogger::printStartupBanner(const SystemConfig& config) {
    Serial.println();
    Serial.println("==========================================================");
    Serial.println("                   FORENSITAP-ESP32                      ");
    Serial.println("  Wireless Forensics & Tamper-Evident Monitoring Node   ");
    Serial.println("==========================================================");
    Serial.printf("Firmware Version : %s (%s)\n", FORENSITAP_VERSION_STR, FORENSITAP_TARGET_HW);
    Serial.printf("Silicon Model    : %s (Rev %u)\n", ESP.getChipModel(), ESP.getChipRevision());
    Serial.printf("CPU Clock        : %u MHz | Dual-Core Xtensa LX6\n", ESP.getCpuFreqMHz());
    Serial.printf("Dynamic Heap     : %u bytes free\n", ESP.getFreeHeap());
    Serial.printf("Initial Mode     : %s (Mode %u)\n", 
                  config.operationalMode == OperatingMode::MODE_STANDALONE ? "STANDALONE_DIAGNOSTICS" : "OTHER",
                  static_cast<uint8_t>(config.operationalMode));
    Serial.printf("Serial Baud Rate : %u bps\n", config.serialBaud);
    Serial.printf("Heartbeat Period : %u ms | Status Interval: %u ms\n",
                  config.heartbeatIntervalMs, config.statusIntervalMs);
    Serial.println("==========================================================");
    Serial.println();
}

void DiagnosticLogger::printSystemStatus(const SystemState& state) {
    Serial.println();
    Serial.println("---------------- [SYSTEM TELEMETRY REPORT] ----------------");
    Serial.printf("Uptime           : %lu ms (%lu sec)\n", millis(), millis() / 1000);
    Serial.printf("Operating State  : Mode %u | Health: %s\n", 
                  static_cast<uint8_t>(state.currentMode),
                  state.isHealthy ? "OPTIMAL" : "DEGRADED");
    Serial.printf("Memory Available : %u bytes dynamic heap\n", ESP.getFreeHeap());
    Serial.printf("Events Processed : %u logged\n", state.totalEventsLogged);
    Serial.printf("Frames Ingested  : %u frames | %u dropped\n", 
                  state.totalFramesObserved, state.droppedFramesCount);
    Serial.println("----------------------------------------------------------");
    Serial.println();
}

void DiagnosticLogger::log(LogLevel level, const char* tag, const char* format, ...) {
    if (level < s_minLevel || level == LogLevel::LOG_LVL_NONE) {
        return;
    }

    char messageBuffer[160];
    va_list args;
    va_start(args, format);
    vsnprintf(messageBuffer, sizeof(messageBuffer), format, args);
    va_end(args);

    // Formatted output: [timestamp_ms] [LEVEL] [TAG] Message
    Serial.printf("[%10lu] [%s] [%-4s] %s\n",
                  millis(),
                  levelToString(level),
                  tag ? tag : "SYS",
                  messageBuffer);
}

void DiagnosticLogger::logEvent(const SystemEvent& event) {
    char eventBuffer[160];
    event.toFormattedString(eventBuffer, sizeof(eventBuffer));
    Serial.println(eventBuffer);
}
