#include "wifi_monitor.h"
#include "feature_engine.h"
#include "detector.h"

// Global singleton instance
ForensiTapWifiMonitor g_wifiMonitor;

// Static member definitions
QueueHandle_t ForensiTapWifiMonitor::s_observationQueue = nullptr;
bool          ForensiTapWifiMonitor::s_isMonitoring = false;
uint8_t       ForensiTapWifiMonitor::s_currentChannel = 11;

volatile uint32_t ForensiTapWifiMonitor::s_totalFrames = 0;
volatile uint32_t ForensiTapWifiMonitor::s_mgmtFrames = 0;
volatile uint32_t ForensiTapWifiMonitor::s_ctrlFrames = 0;
volatile uint32_t ForensiTapWifiMonitor::s_dataFrames = 0;
volatile uint32_t ForensiTapWifiMonitor::s_droppedFrames = 0;
volatile uint32_t ForensiTapWifiMonitor::s_malformedFrames = 0;

ForensiTapWifiMonitor::ForensiTapWifiMonitor()
    : m_trackedDeviceCount(0),
      m_lastRateCalcMillis(0),
      m_lastTotalFrames(0),
      m_currentFrameRate(0.0f) {
    memset(m_deviceTable, 0, sizeof(m_deviceTable));
}

bool ForensiTapWifiMonitor::init(const SystemConfig& config) {
    LOG_INFO("MON", "Initializing Wi-Fi Promiscuous Monitor subsystem...");

    // Allocate bounded FreeRTOS observation queue
    if (!s_observationQueue) {
        s_observationQueue = xQueueCreate(MONITOR_QUEUE_SIZE, sizeof(FrameObservation));
        if (!s_observationQueue) {
            LOG_ERROR("MON", "Failed to allocate observation queue!");
            return false;
        }
    }

    // Initialize bounded device table
    memset(m_deviceTable, 0, sizeof(m_deviceTable));
    m_trackedDeviceCount = 0;

    // Default channel matching active AP or config
    s_currentChannel = config.defaultWifiChannel;

    // Start promiscuous monitoring on default channel
    return startPromiscuous(s_currentChannel);
}

bool ForensiTapWifiMonitor::startPromiscuous(uint8_t channel) {
    if (s_isMonitoring) {
        return true;
    }

    LOG_INFO("MON", "Starting 802.11 promiscuous mode on Channel %u...", channel);

    // Filter configuration: Capture Management and Data frames
    wifi_promiscuous_filter_t filter;
    filter.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA;
    esp_wifi_set_promiscuous_filter(&filter);

    // Register lightweight RX callback
    esp_wifi_set_promiscuous_rx_cb(ForensiTapWifiMonitor::promiscuousRxCallback);

    // Lock to target channel
    s_currentChannel = channel;
    esp_wifi_set_channel(s_currentChannel, WIFI_SECOND_CHAN_NONE);

    // Enable promiscuous capture
    esp_err_t err = esp_wifi_set_promiscuous(true);
    if (err == ESP_OK) {
        s_isMonitoring = true;
        LOG_INFO("MON", "Promiscuous frame capture ACTIVE on Channel %u", s_currentChannel);
        return true;
    } else {
        LOG_ERROR("MON", "esp_wifi_set_promiscuous(true) failed with code 0x%X", err);
        s_isMonitoring = false;
        return false;
    }
}

void ForensiTapWifiMonitor::stopPromiscuous() {
    if (!s_isMonitoring) return;

    esp_wifi_set_promiscuous(false);
    s_isMonitoring = false;
    LOG_INFO("MON", "Promiscuous mode STOPPED.");
}

bool ForensiTapWifiMonitor::isMonitoring() const {
    return s_isMonitoring;
}

void ForensiTapWifiMonitor::setChannel(uint8_t channel) {
    if (channel >= 1 && channel <= 14) {
        s_currentChannel = channel;
        esp_wifi_set_channel(s_currentChannel, WIFI_SECOND_CHAN_NONE);
        LOG_INFO("MON", "Monitor channel set to %u", s_currentChannel);
    }
}

uint8_t ForensiTapWifiMonitor::getChannel() const {
    return s_currentChannel;
}

bool ForensiTapWifiMonitor::getNextObservation(FrameObservation& outObs) {
    if (!s_observationQueue) return false;
    return (xQueueReceive(s_observationQueue, &outObs, 0) == pdTRUE);
}

uint32_t ForensiTapWifiMonitor::getTotalFrames() const { return s_totalFrames; }
uint32_t ForensiTapWifiMonitor::getManagementFrames() const { return s_mgmtFrames; }
uint32_t ForensiTapWifiMonitor::getControlFrames() const { return s_ctrlFrames; }
uint32_t ForensiTapWifiMonitor::getDataFrames() const { return s_dataFrames; }
uint32_t ForensiTapWifiMonitor::getDroppedFrames() const { return s_droppedFrames; }
uint32_t ForensiTapWifiMonitor::getMalformedFrames() const { return s_malformedFrames; }
float ForensiTapWifiMonitor::getCurrentFrameRate() const { return m_currentFrameRate; }

uint16_t ForensiTapWifiMonitor::getUniqueDeviceCount() const {
    return m_trackedDeviceCount;
}

const DeviceRecord* ForensiTapWifiMonitor::getDeviceTable() const {
    return m_deviceTable;
}

bool ForensiTapWifiMonitor::isHealthy() const {
    return s_isMonitoring;
}

bool ForensiTapWifiMonitor::isValidUnicastMac(const uint8_t* mac) {
    if (!mac) return false;

    // Reject all-zeros
    if ((mac[0] | mac[1] | mac[2] | mac[3] | mac[4] | mac[5]) == 0) {
        return false;
    }

    // Reject broadcast (FF:FF:FF:FF:FF:FF)
    if (mac[0] == 0xFF && mac[1] == 0xFF && mac[2] == 0xFF &&
        mac[3] == 0xFF && mac[4] == 0xFF && mac[5] == 0xFF) {
        return false;
    }

    // Reject multicast (least significant bit of first octet is 1)
    if (mac[0] & 0x01) {
        return false;
    }

    return true;
}

void ForensiTapWifiMonitor::updateDeviceTable(const uint8_t* mac, int8_t rssi, uint32_t timestampMs, bool isAp) {
    // 1. Search for existing entry in table
    for (size_t i = 0; i < MAX_TRACKED_DEVICES; ++i) {
        if (m_deviceTable[i].inUse && memcmp(m_deviceTable[i].mac, mac, 6) == 0) {
            m_deviceTable[i].frameCount++;
            m_deviceTable[i].lastSeenMs = timestampMs;
            m_deviceTable[i].lastRssi = rssi;
            if (rssi < m_deviceTable[i].minRssi) m_deviceTable[i].minRssi = rssi;
            if (rssi > m_deviceTable[i].maxRssi) m_deviceTable[i].maxRssi = rssi;
            if (isAp) m_deviceTable[i].isAccessPoint = true;
            return;
        }
    }

    // 2. Find an empty slot if capacity permits
    for (size_t i = 0; i < MAX_TRACKED_DEVICES; ++i) {
        if (!m_deviceTable[i].inUse) {
            memcpy(m_deviceTable[i].mac, mac, 6);
            m_deviceTable[i].frameCount = 1;
            m_deviceTable[i].firstSeenMs = timestampMs;
            m_deviceTable[i].lastSeenMs = timestampMs;
            m_deviceTable[i].lastRssi = rssi;
            m_deviceTable[i].minRssi = rssi;
            m_deviceTable[i].maxRssi = rssi;
            m_deviceTable[i].isAccessPoint = isAp;
            m_deviceTable[i].inUse = true;
            m_trackedDeviceCount++;

            // Notify detector of newly observed wireless device (Rule 3)
            char macStr[18];
            m_deviceTable[i].formatMac(macStr, sizeof(macStr));
            g_detector.notifyNewDevice(macStr, isAp, rssi);
            return;
        }
    }

    // 3. Table full: Evict least recently seen device (LRU eviction)
    size_t oldestIdx = 0;
    uint32_t oldestTime = m_deviceTable[0].lastSeenMs;
    for (size_t i = 1; i < MAX_TRACKED_DEVICES; ++i) {
        if (m_deviceTable[i].lastSeenMs < oldestTime) {
            oldestTime = m_deviceTable[i].lastSeenMs;
            oldestIdx = i;
        }
    }

    memcpy(m_deviceTable[oldestIdx].mac, mac, 6);
    m_deviceTable[oldestIdx].frameCount = 1;
    m_deviceTable[oldestIdx].firstSeenMs = timestampMs;
    m_deviceTable[oldestIdx].lastSeenMs = timestampMs;
    m_deviceTable[oldestIdx].lastRssi = rssi;
    m_deviceTable[oldestIdx].minRssi = rssi;
    m_deviceTable[oldestIdx].maxRssi = rssi;
    m_deviceTable[oldestIdx].isAccessPoint = isAp;
    m_deviceTable[oldestIdx].inUse = true;

    char macStr[18];
    m_deviceTable[oldestIdx].formatMac(macStr, sizeof(macStr));
    g_detector.notifyNewDevice(macStr, isAp, rssi);
}

void ForensiTapWifiMonitor::processObservation(const FrameObservation& obs) {
    // 1. Sanity check frame length bounds (IEEE 802.11 min=10, max=2346 bytes)
    if (obs.length < 10 || obs.length > 2346) {
        s_malformedFrames++;
        return;
    }

    // 2. Sanity check frame type (0=Mgmt, 1=Ctrl, 2=Data, 3=Misc)
    if (obs.frameType > 3) {
        s_malformedFrames++;
        return;
    }

    // 3. Feed statistical feature engine
    g_featureEngine.recordFrame(obs.length, obs.frameType);

    // 4. Extract and track transmitting device
    if (obs.hasSourceMac && isValidUnicastMac(obs.sourceMac)) {
        // Beacon (subtype 8) or Probe Response (subtype 5) in Management frames indicate AP
        bool isAp = (obs.frameType == 0 && (obs.frameSubtype == 8 || obs.frameSubtype == 5));
        updateDeviceTable(obs.sourceMac, obs.rssi, obs.timestampMs, isAp);
    }
}

void ForensiTapWifiMonitor::update(unsigned long currentMillis) {
    // Calculate instantaneous frame rate once per second
    if (currentMillis - m_lastRateCalcMillis >= 1000) {
        unsigned long elapsedMs = currentMillis - m_lastRateCalcMillis;
        uint32_t framesDelta = s_totalFrames - m_lastTotalFrames;

        if (elapsedMs > 0) {
            m_currentFrameRate = (float)framesDelta / ((float)elapsedMs / 1000.0f);
        }

        m_lastTotalFrames = s_totalFrames;
        m_lastRateCalcMillis = currentMillis;
    }

    // Process observations drained from the FreeRTOS queue
    FrameObservation obs;
    size_t processedInSlice = 0;
    while (getNextObservation(obs) && processedInSlice < 32) {
        processObservation(obs);
        processedInSlice++;
    }
}

void ForensiTapWifiMonitor::printDiagnostics() {
    Serial.println("  +-- [Wi-Fi Monitor Subsystem: MON]");
    Serial.printf("  |   Promiscuous Mode : %s (Channel %u)\n", s_isMonitoring ? "ACTIVE" : "STANDBY", s_currentChannel);
    Serial.printf("  |   Observed Total   : %u frames (%.1f fps)\n", s_totalFrames, m_currentFrameRate);
    Serial.printf("  |   Management Frames: %u\n", s_mgmtFrames);
    Serial.printf("  |   Data Frames      : %u\n", s_dataFrames);
    Serial.printf("  |   Control Frames   : %u\n", s_ctrlFrames);
    Serial.printf("  |   Queue Dropped    : %u frames | Malformed: %u\n", s_droppedFrames, s_malformedFrames);
    Serial.printf("  |   Unique Devices   : %u / %u tracked\n", m_trackedDeviceCount, MAX_TRACKED_DEVICES);

    // Print sample of tracked devices
    size_t printed = 0;
    for (size_t i = 0; i < MAX_TRACKED_DEVICES && printed < 3; ++i) {
        if (m_deviceTable[i].inUse) {
            char macStr[18];
            m_deviceTable[i].formatMac(macStr, sizeof(macStr));
            Serial.printf("  |     -> [%s] %s | %u pkts | RSSI: %d dBm\n",
                          macStr,
                          m_deviceTable[i].isAccessPoint ? "AP  " : "STA ",
                          m_deviceTable[i].frameCount,
                          m_deviceTable[i].lastRssi);
            printed++;
        }
    }
    Serial.println("  +------------------------------------");
}

void IRAM_ATTR ForensiTapWifiMonitor::promiscuousRxCallback(void* buf, wifi_promiscuous_pkt_type_t type) {
    if (!buf) return;

    s_totalFrames++;

    switch (type) {
        case WIFI_PKT_MGMT: s_mgmtFrames++; break;
        case WIFI_PKT_CTRL: s_ctrlFrames++; break;
        case WIFI_PKT_DATA: s_dataFrames++; break;
        default: break;
    }

    wifi_promiscuous_pkt_t* pkt = (wifi_promiscuous_pkt_t*)buf;

    FrameObservation obs;
    obs.timestampMs = millis();
    obs.length = pkt->rx_ctrl.sig_len;
    obs.rssi = pkt->rx_ctrl.rssi;
    obs.channel = pkt->rx_ctrl.channel;
    obs.frameType = static_cast<uint8_t>(type);
    obs.frameSubtype = 0;
    obs.retry = false;
    obs.hasSourceMac = false;
    obs.hasDestMac = false;

    // Extract 802.11 MAC Header Metadata if packet length is sufficient
    const uint8_t* payload = pkt->payload;
    if (pkt->rx_ctrl.sig_len >= 24 && payload) {
        // Frame Control field
        obs.frameSubtype = (payload[0] & 0xF0) >> 4;
        obs.retry = ((payload[1] & 0x08) != 0);

        // Addr 1: Destination MAC (bytes 4-9)
        memcpy(obs.destMac, &payload[4], 6);
        obs.hasDestMac = true;

        // Addr 2: Source MAC (bytes 10-15)
        memcpy(obs.sourceMac, &payload[10], 6);
        obs.hasSourceMac = true;
    }

    // Transfer observation to bounded queue (non-blocking from ISR)
    if (s_observationQueue) {
        BaseType_t xHigherPriorityTaskWoken = pdFALSE;
        if (xQueueSendFromISR(s_observationQueue, &obs, &xHigherPriorityTaskWoken) != pdTRUE) {
            s_droppedFrames++;
        }
        if (xHigherPriorityTaskWoken == pdTRUE) {
            portYIELD_FROM_ISR();
        }
    }
}
