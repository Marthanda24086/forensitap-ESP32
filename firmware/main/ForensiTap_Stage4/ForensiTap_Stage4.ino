/*
  Project: ForensiTap-ESP32
  Stage: 4 - Initial Hardware Test
  
  Description:
  Firmware initialization and serial communication verification sketch for
  the ForensiTap-ESP32 appliance. Verifies board boot sequence, serial baud rate,
  core hardware properties, and continuous non-blocking execution.
  
  Hardware: ESP32 DevKit V1 (ESP32-WROOM-32)
  Framework: Arduino ESP32 Core
  Baud Rate: 115200 bps
*/

#include <Arduino.h>

// Timestamp tracking for non-blocking periodic tasks (heartbeat)
unsigned long previousMillis = 0;

// Heartbeat period: 2000 ms (2.0 seconds)
const unsigned long HEARTBEAT_INTERVAL = 2000;

/**
 * @brief Outputs hardware identity and runtime diagnostic information to UART.
 */
void printSystemInformation() {
    Serial.println();
    Serial.println("==================================");
    Serial.println("       FORENSITAP-ESP32");
    Serial.println("==================================");
    Serial.println();
    Serial.println("Hardware initialization: SUCCESS");
    Serial.println();

    // Query silicon properties from the ESP system abstraction layer
    Serial.print("Chip model: ");
    Serial.println(ESP.getChipModel());

    Serial.print("Chip revision: ");
    Serial.println(ESP.getChipRevision());
    Serial.println();

    // Operational clock frequency of the Xtensa dual-core processor
    Serial.print("CPU frequency: ");
    Serial.print(ESP.getCpuFreqMHz());
    Serial.println(" MHz");
    Serial.println();

    // Dynamic memory available for allocations
    Serial.print("Free heap: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" bytes");
    Serial.println();

    Serial.println("==================================");
    Serial.println("System ready.");
    Serial.println();
}

/**
 * @brief System setup routine, executed once upon boot or reset.
 */
void setup() {
    // Initialize primary UART serial bridge at 115200 baud
    Serial.begin(115200);

    // Brief settling delay to allow USB-to-UART bridge (CP2102/CH340) to establish cleanly
    delay(1000);

    // Print diagnostic banner and hardware information
    printSystemInformation();
}

/**
 * @brief Continuous execution loop. Employs non-blocking elapsed time checks.
 */
void loop() {
    unsigned long currentMillis = millis();

    // Safe unsigned subtraction handles millis() rollover (~49.7 days)
    if (currentMillis - previousMillis >= HEARTBEAT_INTERVAL) {
        previousMillis = currentMillis;

        Serial.println("[HEARTBEAT] ForensiTap ESP32 is running.");
    }
}
