#ifndef MODULE_INTERFACE_H
#define MODULE_INTERFACE_H

#include "system_config.h"

/**
 * @file module_interface.h
 * @brief Abstract lifecycle contract for all modular embedded subsystems.
 *
 * ForensiTap-ESP32 Appliance
 *
 * Imposes uniform lifecycle semantics across NetworkManager, WifiMonitor,
 * FeatureEngine, Detector, EvidenceLogger, ApiServer, and StorageManager.
 */

class IModule {
public:
    virtual ~IModule() {}

    /**
     * @brief Returns human-readable module identifier (e.g. "NET", "MON", "DET").
     */
    virtual const char* getName() const = 0;

    /**
     * @brief Performs one-time hardware initialization and buffer pre-allocation.
     * @param config Read-only reference to central system configuration.
     * @return true if initialization succeeded; false otherwise.
     */
    virtual bool init(const SystemConfig& config) = 0;

    /**
     * @brief Periodic non-blocking execution slice called by main loop.
     * @param currentMillis Current monotonic system uptime in milliseconds.
     */
    virtual void update(unsigned long currentMillis) = 0;

    /**
     * @brief Evaluates operational health of the module.
     * @return true if module is functioning within nominal parameters.
     */
    virtual bool isHealthy() const = 0;

    /**
     * @brief Emits subsystem-specific telemetry to diagnostic output.
     */
    virtual void printDiagnostics() = 0;
};

#endif // MODULE_INTERFACE_H
