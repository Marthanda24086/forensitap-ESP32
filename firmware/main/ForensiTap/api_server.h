#ifndef API_SERVER_H
#define API_SERVER_H

#include <Arduino.h>
#include <WebServer.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "system_config.h"
#include "events.h"
#include "network_manager.h"

/**
 * @file api_server.h
 * @brief Lightweight REST HTTP API server for ForensiTap-ESP32.
 *
 * Exposes system telemetry, forensic event logs, feature vectors,
 * and monitoring metrics as JSON endpoints for dashboard and laptop ingestion.
 */

class ForensiTapApiServer : public IModule {
public:
    ForensiTapApiServer();
    virtual ~ForensiTapApiServer() {}

    // IModule Lifecycle Interface Implementation
    virtual const char* getName() const override { return "API"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // Server Control
    void start();
    void stop();
    bool isRunning() const;

private:
    // Route Registration
    void registerRoutes();

    // Endpoint Handlers
    void handleRoot();
    void handleHealth();
    void handleStats();
    void handleDevices();
    void handleAlerts();
    void handleFeatures();
    void handleLogs();
    void handleLogsVerify();
    void handleExport();
    void handleNotFound();

    // Helper utilities
    void sendJsonResponse(int statusCode, const char* jsonPayload);
    void setCorsHeaders();

    WebServer m_server;
    bool      m_isRunning;
    uint32_t  m_totalRequestsHandled;
};

extern ForensiTapApiServer g_apiServer;

#endif // API_SERVER_H
