#include "network_manager.h"

// Static member definitions
WifiState ForensiTapNetworkManager::s_state = WifiState::STATE_IDLE;
IPAddress ForensiTapNetworkManager::s_localIP(0, 0, 0, 0);
int8_t    ForensiTapNetworkManager::s_rssi = 0;
uint8_t   ForensiTapNetworkManager::s_channel = 0;
bool      ForensiTapNetworkManager::s_gotIP = false;

// Global singleton instance
ForensiTapNetworkManager g_networkManager;

ForensiTapNetworkManager::ForensiTapNetworkManager()
    : m_connectStartMillis(0),
      m_lastReconnectAttemptMillis(0),
      m_reconnectCount(0),
      m_autoReconnectEnabled(true) {
    memset(m_ssid, 0, sizeof(m_ssid));
    memset(m_password, 0, sizeof(m_password));
}

bool ForensiTapNetworkManager::init(const SystemConfig& config) {
    LOG_INFO("NET", "Initializing Wi-Fi subsystem in Station Mode...");

    // Copy credentials from configuration header
    strncpy(m_ssid, WIFI_SSID, sizeof(m_ssid) - 1);
    strncpy(m_password, WIFI_PASSWORD, sizeof(m_password) - 1);

    // Register FreeRTOS event listener for asynchronous Wi-Fi stack notifications
    WiFi.onEvent(ForensiTapNetworkManager::onWifiEvent);

    // Disable access point and set pure station mode
    WiFi.mode(WIFI_STA);

    // Check if user has entered real credentials or left defaults
    if (strcmp(m_ssid, "YOUR_WIFI_SSID") == 0 || strlen(m_ssid) == 0) {
        LOG_WARN("NET", "Credentials unconfigured (WIFI_SSID='YOUR_WIFI_SSID').");
        LOG_INFO("NET", "To connect, update 'wifi_credentials.h' with your 2.4 GHz network.");
        s_state = WifiState::STATE_DISABLED;
        return true;
    }

    // Initiate connection attempt
    connect(m_ssid, m_password);
    return true;
}

void ForensiTapNetworkManager::connect(const char* ssid, const char* password) {
    if (!ssid || strlen(ssid) == 0) {
        LOG_ERROR("NET", "Cannot connect: SSID is empty");
        return;
    }

    LOG_INFO("NET", "Initiating non-blocking connection to SSID: [%s]...", ssid);
    s_state = WifiState::STATE_CONNECTING;
    s_gotIP = false;
    m_connectStartMillis = millis();

    // Start ESP32 background connection task
    WiFi.begin(ssid, password);
}

void ForensiTapNetworkManager::disconnect() {
    LOG_INFO("NET", "Disconnecting Wi-Fi interface...");
    m_autoReconnectEnabled = false;
    WiFi.disconnect(true);
    s_state = WifiState::STATE_DISCONNECTED;
}

bool ForensiTapNetworkManager::isConnected() const {
    return (s_state == WifiState::STATE_CONNECTED && s_gotIP);
}

WifiState ForensiTapNetworkManager::getState() const {
    return s_state;
}

IPAddress ForensiTapNetworkManager::getLocalIP() const {
    return isConnected() ? WiFi.localIP() : IPAddress(0, 0, 0, 0);
}

String ForensiTapNetworkManager::getMacAddress() const {
    return WiFi.macAddress();
}

int8_t ForensiTapNetworkManager::getRSSI() const {
    return isConnected() ? WiFi.RSSI() : 0;
}

uint8_t ForensiTapNetworkManager::getChannel() const {
    return isConnected() ? WiFi.channel() : 0;
}

bool ForensiTapNetworkManager::isHealthy() const {
    // Healthy if disabled by configuration, or connected, or actively negotiating
    return (s_state != WifiState::STATE_TIMEOUT);
}

void ForensiTapNetworkManager::update(unsigned long currentMillis) {
    // If Wi-Fi is disabled by configuration (no credentials), nothing to do
    if (s_state == WifiState::STATE_DISABLED || s_state == WifiState::STATE_IDLE) {
        return;
    }

    // Check for connection timeout while negotiating
    if (s_state == WifiState::STATE_CONNECTING) {
        if (currentMillis - m_connectStartMillis > WIFI_CONNECT_TIMEOUT_MS) {
            LOG_WARN("NET", "Connection attempt timed out after %u ms", WIFI_CONNECT_TIMEOUT_MS);
            s_state = WifiState::STATE_TIMEOUT;
            m_lastReconnectAttemptMillis = currentMillis;
            WiFi.disconnect();
        }
        return;
    }

    // Handle non-blocking auto-reconnect if disconnected or timed out
    if (m_autoReconnectEnabled && (s_state == WifiState::STATE_DISCONNECTED || s_state == WifiState::STATE_TIMEOUT)) {
        if (currentMillis - m_lastReconnectAttemptMillis >= WIFI_RECONNECT_INTERVAL_MS) {
            m_lastReconnectAttemptMillis = currentMillis;
            m_reconnectCount++;

            LOG_INFO("NET", "Auto-reconnect attempt #%u to [%s]...", m_reconnectCount, m_ssid);
            connect(m_ssid, m_password);
        }
    }
}

void ForensiTapNetworkManager::printDiagnostics() {
    Serial.println("  +-- [Network Manager Subsystem: NET]");
    Serial.printf("  |   State           : %s\n", 
                  s_state == WifiState::STATE_CONNECTED ? "CONNECTED" :
                  s_state == WifiState::STATE_CONNECTING ? "CONNECTING" :
                  s_state == WifiState::STATE_DISCONNECTED ? "DISCONNECTED" :
                  s_state == WifiState::STATE_TIMEOUT ? "TIMEOUT" : "DISABLED");
    Serial.printf("  |   Station MAC     : %s\n", WiFi.macAddress().c_str());
    if (isConnected()) {
        Serial.printf("  |   IPv4 Address    : %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("  |   Subnet Mask     : %s\n", WiFi.subnetMask().toString().c_str());
        Serial.printf("  |   Gateway         : %s\n", WiFi.gatewayIP().toString().c_str());
        Serial.printf("  |   Active Channel  : %u\n", WiFi.channel());
        Serial.printf("  |   Signal RSSI     : %d dBm\n", WiFi.RSSI());
    } else {
        Serial.printf("  |   Target SSID     : %s\n", m_ssid);
        Serial.printf("  |   Reconnect Retries: %u\n", m_reconnectCount);
    }
    Serial.println("  +------------------------------------");
}

void ForensiTapNetworkManager::onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
    switch (event) {
        case ARDUINO_EVENT_WIFI_STA_START:
            LOG_DEBUG("NET", "Wi-Fi Station peripheral started");
            break;

        case ARDUINO_EVENT_WIFI_STA_CONNECTED:
            LOG_INFO("NET", "Associated with AP. Negotiating DHCP IP lease...");
            break;

        case ARDUINO_EVENT_WIFI_STA_GOT_IP: {
            s_state = WifiState::STATE_CONNECTED;
            s_gotIP = true;
            s_localIP = IPAddress(info.got_ip.ip_info.ip.addr);
            s_channel = WiFi.channel();
            s_rssi = WiFi.RSSI();

            LOG_INFO("NET", "DHCP Lease Granted! IPv4: %s | Channel: %u | RSSI: %d dBm",
                     s_localIP.toString().c_str(), s_channel, s_rssi);
            break;
        }

        case ARDUINO_EVENT_WIFI_STA_DISCONNECTED: {
            s_state = WifiState::STATE_DISCONNECTED;
            s_gotIP = false;
            uint8_t reason = info.wifi_sta_disconnected.reason;
            LOG_WARN("NET", "Station disconnected from AP (Reason code: %u)", reason);
            break;
        }

        default:
            break;
    }
}
