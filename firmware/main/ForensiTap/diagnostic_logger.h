#ifndef DIAGNOSTIC_LOGGER_H
#define DIAGNOSTIC_LOGGER_H

#include <Arduino.h>
#include "system_config.h"
#include "events.h"

/**
 * @file diagnostic_logger.h
 * @brief Structured serial diagnostic logging facility.
 *
 * ForensiTap-ESP32 Appliance
 */

enum class LogLevel : uint8_t {
    LOG_LVL_DEBUG = 0,
    LOG_LVL_INFO,
    LOG_LVL_WARN,
    LOG_LVL_ERROR,
    LOG_LVL_NONE
};

class DiagnosticLogger {
public:
    static void init(uint32_t baudRate);
    static void setLogLevel(LogLevel level);
    static LogLevel getLogLevel();

    static void printStartupBanner(const SystemConfig& config);
    static void printSystemStatus(const SystemState& state);

    static void log(LogLevel level, const char* tag, const char* format, ...) __attribute__((format(printf, 3, 4)));
    static void logEvent(const SystemEvent& event);

private:
    static LogLevel s_minLevel;
    static const char* levelToString(LogLevel level);
};

// Convenient logging macros
#define LOG_DEBUG(tag, ...) DiagnosticLogger::log(LogLevel::LOG_LVL_DEBUG, tag, __VA_ARGS__)
#define LOG_INFO(tag, ...)  DiagnosticLogger::log(LogLevel::LOG_LVL_INFO,  tag, __VA_ARGS__)
#define LOG_WARN(tag, ...)  DiagnosticLogger::log(LogLevel::LOG_LVL_WARN,  tag, __VA_ARGS__)
#define LOG_ERROR(tag, ...) DiagnosticLogger::log(LogLevel::LOG_LVL_ERROR, tag, __VA_ARGS__)

#endif // DIAGNOSTIC_LOGGER_H
