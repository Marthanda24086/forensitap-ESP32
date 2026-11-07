#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "events.h"
#include "wifi_credentials.h"

/**
 * @file network_manager.h
 * @brief Wi-Fi station connectivity and event-driven network manager.
 *
 * ForensiTap-ESP32 Appliance
 *
 * Note: Class renamed to ForensiTapNetworkManager to resolve naming collision
 * with the internal NetworkManager class introduced in ESP32 Arduino Core 3.x.
 */

enum class WifiState : uint8_t {
    STATE_IDLE = 0,
    STATE_CONNECTING,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_TIMEOUT,
    STATE_DISABLED
};

class ForensiTapNetworkManager : public IModule {
public:
    ForensiTapNetworkManager();
    virtual ~ForensiTapNetworkManager() {}

    // IModule Lifecycle Interface Implementation
    virtual const char* getName() const override { return "NET"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // Network Operations
    void connect(const char* ssid, const char* password);
    void disconnect();
    bool isConnected() const;

    // Network Telemetry
    WifiState getState() const;
    IPAddress getLocalIP() const;
    String getMacAddress() const;
    int8_t getRSSI() const;
    uint8_t getChannel() const;

private:
    // Wi-Fi Event Handler Callback
    static void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info);

    // Internal State
    static WifiState s_state;
    static IPAddress s_localIP;
    static int8_t    s_rssi;
    static uint8_t   s_channel;
    static bool      s_gotIP;

    char m_ssid[33];
    char m_password[65];

    unsigned long m_connectStartMillis;
    unsigned long m_lastReconnectAttemptMillis;
    uint32_t      m_reconnectCount;
    bool          m_autoReconnectEnabled;
};

// Singleton reference for global dispatch
extern ForensiTapNetworkManager g_networkManager;

#endif // NETWORK_MANAGER_H
