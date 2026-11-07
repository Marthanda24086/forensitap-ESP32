#ifndef WIFI_CREDENTIALS_H
#define WIFI_CREDENTIALS_H

/**
 * @file wifi_credentials.h
 * @brief User Wi-Fi network credentials configuration.
 *
 * ForensiTap-ESP32 Appliance
 *
 * IMPORTANT SECURITY PRACTICE:
 * Configure your actual Wi-Fi SSID and Password here for Stage 6 testing.
 * This file contains credentials and should never be committed to public repositories.
 */

// Replace with your 2.4 GHz Wi-Fi network SSID (ESP32 only supports 2.4 GHz)
#ifndef WIFI_SSID
#define WIFI_SSID "Sahashra Technologies-2.4G"
#endif

// Replace with your Wi-Fi WPA2/WPA3 password
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "15112021"
#endif

// Connection attempt timeout in milliseconds (15 seconds)
#define WIFI_CONNECT_TIMEOUT_MS 15000

// Non-blocking reconnection retry interval (10 seconds)
#define WIFI_RECONNECT_INTERVAL_MS 10000

#endif // WIFI_CREDENTIALS_H
