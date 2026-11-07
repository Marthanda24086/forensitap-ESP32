#ifndef WIFI_MONITOR_H
#define WIFI_MONITOR_H

#include <Arduino.h>
#include <esp_wifi.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "system_config.h"
#include "events.h"

/**
 * @file wifi_monitor.h
 * @brief 802.11 Promiscuous Frame Sniffer, Metadata Processor & Device Tracker.
 *
 * ForensiTap-ESP32 Appliance
 */

// Bounded queue and table capacities
#define MONITOR_QUEUE_SIZE        64
#define MAX_TRACKED_DEVICES       32

/**
 * @brief Compact, fixed-size 802.11 frame observation record.
 */
struct FrameObservation {
    uint32_t timestampMs;
    uint8_t  sourceMac[6];
    uint8_t  destMac[6];
    uint8_t  frameType;      ///< 0 = Management, 1 = Control, 2 = Data, 3 = Misc
    uint8_t  frameSubtype;   ///< Subtype (e.g. 0x08 = Beacon, 0x0C = Deauth)
    uint16_t length;         ///< Packet wire length in bytes
    int8_t   rssi;           ///< Received signal strength in dBm
    uint8_t  channel;        ///< Primary radio channel
    bool     retry;          ///< Retry bit in 802.11 header
    bool     hasSourceMac;   ///< True if source address extracted
    bool     hasDestMac;     ///< True if destination address extracted
};

/**
 * @brief Bounded record tracking an observed wireless station or access point.
 */
struct DeviceRecord {
    uint8_t  mac[6];
    uint32_t frameCount;
    uint32_t firstSeenMs;
    uint32_t lastSeenMs;
    int8_t   lastRssi;
    int8_t   minRssi;
    int8_t   maxRssi;
    bool     isAccessPoint;
    bool     inUse;

    void formatMac(char* outStr, size_t maxLen) const {
        if (!outStr || maxLen < 18) return;
        snprintf(outStr, maxLen, "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    }
};

class ForensiTapWifiMonitor : public IModule {
public:
    ForensiTapWifiMonitor();
    virtual ~ForensiTapWifiMonitor() {}

    // IModule Lifecycle Interface
    virtual const char* getName() const override { return "MON"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // Monitor Control
    bool startPromiscuous(uint8_t channel);
    void stopPromiscuous();
    bool isMonitoring() const;
    void setChannel(uint8_t channel);
    uint8_t getChannel() const;

    // Queue Retrieval
    bool getNextObservation(FrameObservation& outObs);

    // Monitoring Statistics
    uint32_t getTotalFrames() const;
    uint32_t getManagementFrames() const;
    uint32_t getControlFrames() const;
    uint32_t getDataFrames() const;
    uint32_t getDroppedFrames() const;
    uint32_t getMalformedFrames() const;
    float    getCurrentFrameRate() const;

    // Device Tracking API
    uint16_t getUniqueDeviceCount() const;
    const DeviceRecord* getDeviceTable() const;
    uint16_t getMaxDeviceCapacity() const { return MAX_TRACKED_DEVICES; }

private:
    // Metadata Processing Pipeline
    void processObservation(const FrameObservation& obs);
    void updateDeviceTable(const uint8_t* mac, int8_t rssi, uint32_t timestampMs, bool isAp);
    static bool isValidUnicastMac(const uint8_t* mac);

    // ESP-IDF Promiscuous RX Callback
    static void promiscuousRxCallback(void* buf, wifi_promiscuous_pkt_type_t type);

    static QueueHandle_t s_observationQueue;
    static bool          s_isMonitoring;
    static uint8_t       s_currentChannel;

    // Atomic statistical counters
    static volatile uint32_t s_totalFrames;
    static volatile uint32_t s_mgmtFrames;
    static volatile uint32_t s_ctrlFrames;
    static volatile uint32_t s_dataFrames;
    static volatile uint32_t s_droppedFrames;
    static volatile uint32_t s_malformedFrames;

    // Bounded Device Table
    DeviceRecord m_deviceTable[MAX_TRACKED_DEVICES];
    uint16_t     m_trackedDeviceCount;

    // Rate calculation state
    unsigned long m_lastRateCalcMillis;
    uint32_t      m_lastTotalFrames;
    float         m_currentFrameRate;
};

extern ForensiTapWifiMonitor g_wifiMonitor;

#endif // WIFI_MONITOR_H
