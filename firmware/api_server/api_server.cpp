#include "api_server.h"
#include "wifi_monitor.h"
#include "feature_engine.h"
#include "detector.h"
#include "evidence_logger.h"

// Global singleton instance
ForensiTapApiServer g_apiServer;

ForensiTapApiServer::ForensiTapApiServer()
    : m_server(80),
      m_isRunning(false),
      m_totalRequestsHandled(0) {
}

bool ForensiTapApiServer::init(const SystemConfig& config) {
    LOG_INFO("API", "Initializing REST HTTP API Server on port 80...");
    registerRoutes();
    return true;
}

void ForensiTapApiServer::start() {
    if (m_isRunning) return;

    m_server.begin();
    m_isRunning = true;
    LOG_INFO("API", "HTTP Server listening on http://%s:80", 
             g_networkManager.getLocalIP().toString().c_str());
}

void ForensiTapApiServer::stop() {
    if (!m_isRunning) return;

    m_server.stop();
    m_isRunning = false;
    LOG_INFO("API", "HTTP Server stopped.");
}

bool ForensiTapApiServer::isRunning() const {
    return m_isRunning;
}

bool ForensiTapApiServer::isHealthy() const {
    return true;
}

void ForensiTapApiServer::update(unsigned long currentMillis) {
    // Automatically start HTTP service once Wi-Fi acquires an IP
    if (!m_isRunning && g_networkManager.isConnected()) {
        start();
    } else if (m_isRunning && !g_networkManager.isConnected()) {
        // Wi-Fi dropped; pause server to avoid stalled socket binds
        stop();
        return;
    }

    if (m_isRunning) {
        m_server.handleClient();
    }
}

void ForensiTapApiServer::printDiagnostics() {
    Serial.println("  +-- [API Server Subsystem: API]");
    Serial.printf("  |   Status          : %s (Port 80)\n", m_isRunning ? "ACTIVE" : "INACTIVE");
    Serial.printf("  |   Requests Served : %u\n", m_totalRequestsHandled);
    Serial.println("  +------------------------------------");
}

void ForensiTapApiServer::setCorsHeaders() {
    m_server.sendHeader("Access-Control-Allow-Origin", "*");
    m_server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    m_server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void ForensiTapApiServer::sendJsonResponse(int statusCode, const char* jsonPayload) {
    setCorsHeaders();
    m_server.send(statusCode, "application/json", jsonPayload);
    m_totalRequestsHandled++;
}

void ForensiTapApiServer::registerRoutes() {
    m_server.on("/", HTTP_GET, [this]() { handleRoot(); });
    m_server.on("/api/health", HTTP_GET, [this]() { handleHealth(); });
    m_server.on("/api/stats", HTTP_GET, [this]() { handleStats(); });
    m_server.on("/api/devices", HTTP_GET, [this]() { handleDevices(); });
    m_server.on("/api/alerts", HTTP_GET, [this]() { handleAlerts(); });
    m_server.on("/api/features", HTTP_GET, [this]() { handleFeatures(); });
    m_server.on("/api/logs", HTTP_GET, [this]() { handleLogs(); });
    m_server.on("/api/logs/verify", HTTP_GET, [this]() { handleLogsVerify(); });
    m_server.on("/api/export", HTTP_GET, [this]() { handleExport(); });

    // Handle CORS preflight requests
    m_server.onNotFound([this]() {
        if (m_server.method() == HTTP_OPTIONS) {
            setCorsHeaders();
            m_server.send(204);
        } else {
            handleNotFound();
        }
    });
}

// =============================================================================
// ENDPOINT IMPLEMENTATIONS
// =============================================================================

/**
 * @brief GET /
 * Root endpoint returning service identification.
 */
void ForensiTapApiServer::handleRoot() {
    char buf[256];
    snprintf(buf, sizeof(buf),
             "{\"app\":\"ForensiTap-ESP32\",\"version\":\"%s\",\"status\":\"ONLINE\",\"docs\":\"/api/health\"}",
             FORENSITAP_VERSION_STR);
    sendJsonResponse(200, buf);
}

/**
 * @brief GET /api/health
 * Returns core system health, uptime, version, and memory.
 */
void ForensiTapApiServer::handleHealth() {
    char buf[384];
    unsigned long uptimeSec = millis() / 1000;
    snprintf(buf, sizeof(buf),
             "{"
             "\"status\":\"OPTIMAL\","
             "\"uptime_ms\":%lu,"
             "\"uptime_sec\":%lu,"
             "\"firmware_version\":\"%s\","
             "\"hardware\":\"%s\","
             "\"free_heap_bytes\":%u,"
             "\"wifi_connected\":%s,"
             "\"ip_address\":\"%s\","
             "\"wifi_channel\":%u,"
             "\"rssi_dbm\":%d"
             "}",
             millis(),
             uptimeSec,
             FORENSITAP_VERSION_STR,
             FORENSITAP_TARGET_HW,
             ESP.getFreeHeap(),
             g_networkManager.isConnected() ? "true" : "false",
             g_networkManager.getLocalIP().toString().c_str(),
             g_networkManager.getChannel(),
             g_networkManager.getRSSI());
    sendJsonResponse(200, buf);
}

/**
 * @brief GET /api/stats
 * Returns frame monitoring metrics and network counters directly from WifiMonitor.
 */
void ForensiTapApiServer::handleStats() {
    char buf[400];
    snprintf(buf, sizeof(buf),
             "{"
             "\"monitoring_status\":\"%s\","
             "\"active_channel\":%u,"
             "\"total_observed_frames\":%u,"
             "\"current_frame_rate\":%.1f,"
             "\"unique_observed_devices\":%u,"
             "\"management_frame_count\":%u,"
             "\"data_frame_count\":%u,"
             "\"control_frame_count\":%u,"
             "\"dropped_frames_count\":%u,"
             "\"malformed_frames_count\":%u"
             "}",
             g_wifiMonitor.isMonitoring() ? "ACTIVE" : "STANDBY",
             g_wifiMonitor.getChannel(),
             g_wifiMonitor.getTotalFrames(),
             g_wifiMonitor.getCurrentFrameRate(),
             g_wifiMonitor.getUniqueDeviceCount(),
             g_wifiMonitor.getManagementFrames(),
             g_wifiMonitor.getDataFrames(),
             g_wifiMonitor.getControlFrames(),
             g_wifiMonitor.getDroppedFrames(),
             g_wifiMonitor.getMalformedFrames());
    sendJsonResponse(200, buf);
}

/**
 * @brief GET /api/devices
 * Streams the list of observed 802.11 MAC addresses, frame counts, and signal statistics.
 */
void ForensiTapApiServer::handleDevices() {
    setCorsHeaders();
    m_server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    m_server.send(200, "application/json", "");

    char headerBuf[64];
    uint16_t count = g_wifiMonitor.getUniqueDeviceCount();
    snprintf(headerBuf, sizeof(headerBuf), "{\"count\":%u,\"devices\":[", count);
    m_server.sendContent(headerBuf);

    const DeviceRecord* table = g_wifiMonitor.getDeviceTable();
    uint16_t capacity = g_wifiMonitor.getMaxDeviceCapacity();
    bool first = true;

    char devBuf[200];
    char macStr[18];

    for (uint16_t i = 0; i < capacity; ++i) {
        if (table[i].inUse) {
            table[i].formatMac(macStr, sizeof(macStr));
            snprintf(devBuf, sizeof(devBuf),
                     "%s{\"mac\":\"%s\",\"frame_count\":%u,\"first_seen_ms\":%u,\"last_seen_ms\":%u,"
                     "\"last_rssi_dbm\":%d,\"min_rssi_dbm\":%d,\"max_rssi_dbm\":%d,\"is_ap\":%s}",
                     first ? "" : ",",
                     macStr,
                     table[i].frameCount,
                     table[i].firstSeenMs,
                     table[i].lastSeenMs,
                     table[i].lastRssi,
                     table[i].minRssi,
                     table[i].maxRssi,
                     table[i].isAccessPoint ? "true" : "false");
            m_server.sendContent(devBuf);
            first = false;
        }
    }

    m_server.sendContent("]}");
    m_server.sendContent(""); // Terminate chunked transfer
    m_totalRequestsHandled++;
}

/**
 * @brief GET /api/alerts
 * Returns recent security alerts and anomaly events directly from ForensiTapDetector.
 */
void ForensiTapApiServer::handleAlerts() {
    setCorsHeaders();
    m_server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    m_server.send(200, "application/json", "");

    char headerBuf[64];
    uint16_t count = g_detector.getAlertCount();
    snprintf(headerBuf, sizeof(headerBuf), "{\"count\":%u,\"alerts\":[", count);
    m_server.sendContent(headerBuf);

    const SecurityAlert* alerts = g_detector.getAlerts();
    bool first = true;
    char alertBuf[240];

    for (uint16_t i = 0; i < count; ++i) {
        snprintf(alertBuf, sizeof(alertBuf),
                 "%s{\"event_id\":%u,\"timestamp\":%u,\"event_type\":\"%s\",\"severity\":\"%s\",\"description\":\"%s\"}",
                 first ? "" : ",",
                 alerts[i].eventId,
                 alerts[i].timestampMs,
                 eventTypeToString(alerts[i].type),
                 eventSeverityToString(alerts[i].severity),
                 alerts[i].description);
        m_server.sendContent(alertBuf);
        first = false;
    }

    m_server.sendContent("]}");
    m_server.sendContent(""); // Terminate chunked transfer
    m_totalRequestsHandled++;
}

/**
 * @brief GET /api/features
 * Returns latest statistical feature vector from FeatureEngine.
 */
void ForensiTapApiServer::handleFeatures() {
    const FeatureVector& feat = g_featureEngine.getLatestFeatures();

    char buf[540];
    snprintf(buf, sizeof(buf),
             "{"
             "\"window_duration_sec\":%u,"
             "\"frame_rate\":%.2f,"
             "\"byte_rate\":%.2f,"
             "\"average_frame_size\":%.2f,"
             "\"unique_peers\":%u,"
             "\"management_frame_ratio\":%.3f,"
             "\"traffic_burst_score\":%.2f,"
             "\"deauth_rate\":%.2f,"
             "\"disassoc_rate\":%.2f,"
             "\"deauth_ratio\":%.3f,"
             "\"beacon_rate\":%.2f,"
             "\"baseline\":{"
             "\"warmup_ready\":%s,"
             "\"mean_frame_rate\":%.2f,"
             "\"ewma_mean_frame_rate\":%.2f,"
             "\"std_frame_rate\":%.2f,"
             "\"frame_rate_zscore\":%.2f"
             "}"
             "}",
             feat.windowDurationSec,
             feat.frameRate,
             feat.byteRate,
             feat.avgFrameSize,
             feat.uniquePeers,
             feat.managementRatio,
             feat.burstScore,
             feat.deauthRate,
             feat.disassocRate,
             feat.deauthRatio,
             feat.beaconRate,
             feat.baselineReady ? "true" : "false",
             feat.baselineMeanRate,
             feat.baselineEwmaMean,
             feat.baselineStdDevRate,
             feat.rateDeviationZScore);
    sendJsonResponse(200, buf);
}

/**
 * @brief GET /api/logs
 * Returns recent forensic log events sealed in the SHA-256 evidence chain.
 */
void ForensiTapApiServer::handleLogs() {
    setCorsHeaders();
    m_server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    m_server.send(200, "application/json", "");

    uint16_t stored = g_evidenceLogger.getStoredBlockCount();
    uint32_t total = g_evidenceLogger.getTotalBlocksCreated();
    ChainVerificationResult ver = g_evidenceLogger.verifyChainIntegrity();

    char headerBuf[256];
    snprintf(headerBuf, sizeof(headerBuf),
             "{\"chain_valid\":%s,\"total_blocks\":%u,\"stored_count\":%u,\"genesis_hash\":\"%s\",\"tip_hash\":\"%s\",\"blocks\":[",
             ver.isValid ? "true" : "false",
             total,
             stored,
             g_evidenceLogger.getGenesisHash(),
             g_evidenceLogger.getTipHash());
    m_server.sendContent(headerBuf);

    const EvidenceBlock* blocks = g_evidenceLogger.getStoredBlocks();
    char blockBuf[384];
    for (uint16_t i = 0; i < stored; ++i) {
        snprintf(blockBuf, sizeof(blockBuf),
                 "%s{"
                 "\"index\":%u,"
                 "\"timestamp_ms\":%u,"
                 "\"event_type\":\"%s\","
                 "\"severity\":\"%s\","
                 "\"description\":\"%s\","
                 "\"prev_hash\":\"%s\","
                 "\"block_hash\":\"%s\""
                 "}",
                 (i == 0) ? "" : ",",
                 blocks[i].index,
                 blocks[i].timestampMs,
                 blocks[i].eventType,
                 blocks[i].severity,
                 blocks[i].description,
                 blocks[i].prevHash,
                 blocks[i].blockHash);
        m_server.sendContent(blockBuf);
    }

    m_server.sendContent("]}");
    m_server.sendContent(""); // Terminate chunked transfer
    m_totalRequestsHandled++;
}

/**
 * @brief GET /api/logs/verify
 * Executes cryptographic verification of the in-memory SHA-256 hash chain.
 */
void ForensiTapApiServer::handleLogsVerify() {
    ChainVerificationResult ver = g_evidenceLogger.verifyChainIntegrity();
    char buf[384];
    snprintf(buf, sizeof(buf),
             "{"
             "\"status\":\"%s\","
             "\"chain_intact\":%s,"
             "\"blocks_checked\":%u,"
             "\"total_blocks_created\":%u,"
             "\"failed_index\":%u,"
             "\"failure_reason\":\"%s\","
             "\"genesis_hash\":\"%s\","
             "\"tip_hash\":\"%s\""
             "}",
             ver.isValid ? "VALID" : "TAMPERED",
             ver.isValid ? "true" : "false",
             ver.checkedBlocks,
             g_evidenceLogger.getTotalBlocksCreated(),
             ver.failedIndex,
             ver.failureReason,
             g_evidenceLogger.getGenesisHash(),
             g_evidenceLogger.getTipHash());
    sendJsonResponse(ver.isValid ? 200 : 409, buf);
}

/**
 * @brief GET /api/export
 * Exports logs in JSON or CSV format based on query param (?format=json|csv).
 */
void ForensiTapApiServer::handleExport() {
    String format = m_server.arg("format");
    setCorsHeaders();

    uint16_t stored = g_evidenceLogger.getStoredBlockCount();
    const EvidenceBlock* blocks = g_evidenceLogger.getStoredBlocks();

    if (format.equalsIgnoreCase("csv")) {
        m_server.sendHeader("Content-Disposition", "attachment; filename=\"forensitap_evidence.csv\"");
        m_server.setContentLength(CONTENT_LENGTH_UNKNOWN);
        m_server.send(200, "text/csv", "");

        m_server.sendContent("index,timestamp_ms,event_type,severity,description,prev_hash,block_hash\n");
        char rowBuf[384];
        for (uint16_t i = 0; i < stored; ++i) {
            snprintf(rowBuf, sizeof(rowBuf),
                     "%u,%u,\"%s\",\"%s\",\"%s\",\"%s\",\"%s\"\n",
                     blocks[i].index,
                     blocks[i].timestampMs,
                     blocks[i].eventType,
                     blocks[i].severity,
                     blocks[i].description,
                     blocks[i].prevHash,
                     blocks[i].blockHash);
            m_server.sendContent(rowBuf);
        }
        m_server.sendContent(""); // Terminate chunked transfer
        m_totalRequestsHandled++;
    } else {
        handleLogs();
    }
}

/**
 * @brief 404 Not Found Handler with JSON error payload.
 */
void ForensiTapApiServer::handleNotFound() {
    char buf[160];
    snprintf(buf, sizeof(buf),
             "{\"error\":\"NOT_FOUND\",\"path\":\"%s\",\"message\":\"Endpoint does not exist\"}",
             m_server.uri().c_str());
    sendJsonResponse(404, buf);
}
