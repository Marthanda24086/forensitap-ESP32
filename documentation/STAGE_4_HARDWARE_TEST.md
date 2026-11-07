# Stage 4: Initial Hardware Test & Serial Verification

## 1. Document Overview

This technical document details the design, rationale, execution, and troubleshooting procedures for **Stage 4** of the **ForensiTap-ESP32** project: *Initial Hardware Firmware and Serial Communication Verification*.

The primary objective of this stage is to establish a deterministic baseline: confirming that the development environment (toolchain, drivers, and USB interface) can compile code, flash the microcontroller, and exchange serial telemetry with the host workstation without runtime exceptions or blocking loops.

---

## 2. Firmware Architecture & Technical Concepts

The firmware file is located at `firmware/main/ForensiTap_Stage4.ino`.

### 2.1 What the Firmware Does

The Stage 4 firmware performs a structured bootstrap check:
1. Configures the hardware Universal Asynchronous Receiver-Transmitter (UART0) peripheral for 8-N-1 serial communication at 115,200 baud.
2. Pauses briefly (1000 ms) to allow the USB-to-UART bridge converter (e.g., Silicon Labs CP2102 or WCH CH340) and host terminal buffers to stabilize after a DTR/RTS hardware reset.
3. Queries ESP32 hardware registers via the ESP system API (`ESP.getChipModel()`, `ESP.getChipRevision()`, `ESP.getCpuFreqMHz()`, `ESP.getFreeHeap()`).
4. Emits a structured diagnostic banner containing these system parameters.
5. Transitions into an infinite runtime loop emitting a periodic heartbeat log (`[HEARTBEAT] ForensiTap ESP32 is running.`) every 2000 milliseconds using non-blocking timing.

### 2.2 Why `Serial.begin(115200)` is Used

- **Baud Rate Definition:** Baud rate designates the modulation rate in symbols (bits) per second over the serial bus. 115,200 baud transfers 11,520 bytes per second (under standard 10-bit framing: 1 start bit, 8 data bits, 0 parity bits, 1 stop bit).
- **ESP32 Standard:** 115,200 baud is the de-facto standard default for modern 32-bit microcontrollers. While the ESP32 first-stage bootloader prints initial ROM messages at 115,200 or 74,880 baud (depending on the crystal oscillator frequency: 40 MHz vs. 26 MHz), configuring the application UART to 115,200 baud ensures consistent terminal readability without baud switching.
- **Throughput vs. Reliability:** Higher baud rates (such as 921,600) can introduce bit errors over cheap, unshielded micro-USB cables. Lower baud rates (such as 9,600) introduce unacceptable transmission latency, stalling CPU execution when serial buffers saturate. 115,200 baud provides optimal balance between high throughput and robust physical-layer noise immunity.

### 2.3 Role of `setup()`

In the Arduino/ESP32 framework, `setup()` is invoked exactly once by the core task (`app_main()`) after FreeRTOS scheduler initialization:
- Used for static hardware configuration, peripheral clock gating, pin mode assignments, and communication bus establishment.
- In `ForensiTap_Stage4.ino`, `setup()` initializes the UART peripheral, introduces the settling window, and calls `printSystemInformation()`.

### 2.4 Role of `loop()`

Following the completion of `setup()`, the underlying FreeRTOS task invokes `loop()` continuously inside a `for(;;)` construct:
- Contains repetitive, operational logic that must run for the lifetime of the embedded device.
- It must never execute long, blocking operations that starve low-level FreeRTOS tasks (such as Wi-Fi threads or the task watchdog timer `IDLE0`).

### 2.5 Role of `millis()`

- `millis()` returns the number of milliseconds elapsed since the ESP32 booted or was last reset.
- It is backed by a 64-bit hardware timer running under FreeRTOS tick counters, returned as an `unsigned long` (32-bit unsigned integer on 32-bit systems).
- It provides a monotonic reference clock for measuring real-time intervals without halting the processor.

### 2.6 Why Non-Blocking Timing is Essential

Using `delay(2000)` in the `loop()` halts instruction execution completely for two full seconds. During a blocking delay:
- The CPU cannot sample I/O pins, process incoming packets, or evaluate state machines.
- In future stages of ForensiTap-ESP32, promiscuous Wi-Fi frame monitoring and Hall-effect tamper detection will require microsecond-scale responsiveness. A blocking delay would cause massive packet drops and missed physical tampering events.

**Non-blocking timing implementation:**
```cpp
unsigned long currentMillis = millis();
if (currentMillis - previousMillis >= HEARTBEAT_INTERVAL) {
    previousMillis = currentMillis;
    // Execute periodic task
}
```
**Handling `millis()` Rollover:**
Because `unsigned long` in C++ is a 32-bit unsigned integer (`uint32_t`), `millis()` will overflow and roll over from `4,294,967,295` back to `0` after approximately 49.71 days of continuous operation.
Due to two's complement unsigned modular arithmetic, `(currentMillis - previousMillis)` evaluates correctly even when `currentMillis` rolls over to a small number, provided both operands are `unsigned long`. This guarantees that the heartbeat loop will never freeze or behave erratically across the rollover boundary.

### 2.7 Decoding ESP32 Hardware Information

The startup diagnostics report four critical hardware properties:

1. **`ESP.getChipModel()`**:
   - Identifies the specific Espressif silicon variant inside the metal RF shield.
   - For an ESP32-WROOM-32 module on a DevKit V1, this typically returns `ESP32-D0WDQ6` or `ESP32-D0WD-V3` (dual-core Xtensa LX6 architecture with integrated Wi-Fi and Bluetooth).
2. **`ESP.getChipRevision()`**:
   - Reports the silicon die revision number (e.g., `1`, `2`, or `3`).
   - Revision 3 includes hardware errata fixes for peripheral bugs present in early revisions (e.g., PSRAM cache issues and ADC non-linearities).
3. **`ESP.getCpuFreqMHz()`**:
   - Reports the current operational frequency of the Xtensa cores. Standard ESP32 default is 240 MHz (can also operate at 160 MHz or 80 MHz for power conservation). High-throughput packet capture and cryptographic hashing in later stages benefit from the full 240 MHz ceiling.
4. **`ESP.getFreeHeap()`**:
   - Reports the instantaneous dynamic RAM (DRAM) available for heap allocations (`malloc()` / `new`).
   - A standard ESP32 has approximately 320 KB of usable internal SRAM. After FreeRTOS and internal system allocations, `getFreeHeap()` typically reports ~280 KB to ~300 KB free. Tracking this metric confirms memory stability before introducing packet queues.

---

## 3. Step-by-Step Hardware Testing Procedure

### Step 1: Physical Connection
1. Connect the ESP32 DevKit V1 board to your Windows laptop using a known-good micro-USB data cable.
   > **Note:** Ensure the cable has internal data lines. "Charge-only" cables will power the board LED but will not enumerate as a COM port.

### Step 2: Open Sketch in Arduino IDE 2.x
1. Launch **Arduino IDE 2.x**.
2. Go to **File -> Open...** and navigate to:
   `D:\forensitap-ESP32\firmware\main\ForensiTap_Stage4.ino`
   *(If Arduino IDE prompts that the file should be in a folder named `ForensiTap_Stage4`, you may allow it to create the enclosing folder or open it directly within the project tree).*

### Step 3: Board Selection
1. Open the board dropdown at the top of Arduino IDE or navigate to **Tools -> Board -> esp32**.
2. Select either:
   - **DOIT ESP32 DEVKIT V1** (standard for 30-pin and 36-pin DevKit V1 clones), OR
   - **ESP32 Dev Module** (generic configuration compatible with all ESP32-WROOM-32 boards).
3. Keep standard settings:
   - CPU Frequency: `240MHz (WiFi/BT)`
   - Flash Frequency: `80MHz`
   - Flash Mode: `QIO`
   - Upload Speed: `921600` (or `115200` if flashing stability issues occur)
   - Core Debug Level: `None`

### Step 4: COM Port Identification & Selection
1. On Windows, right-click the Start Menu and open **Device Manager**.
2. Expand the **Ports (COM & LPT)** section.
3. Look for a device labeled:
   - `Silicon Labs CP210x USB to UART Bridge (COMx)` OR
   - `USB-SERIAL CH340 (COMx)`
4. Note the port number (e.g., `COM3`, `COM4`, `COM7`).
5. In Arduino IDE, navigate to **Tools -> Port** and check the identified COM port.

### Step 5: Verification (Compilation)
1. Click the **Verify** button (the Checkmark icon in the top toolbar) or press `Ctrl + R`.
2. Observe the bottom output console.
3. The build should finish with status:
   `Done compiling.` along with memory usage percentages (typically ~3% of program storage and ~4% of dynamic memory).

### Step 6: Firmware Upload
1. Click the **Upload** button (the Right Arrow icon in the top toolbar) or press `Ctrl + U`.
2. The IDE will compile and invoke `esptool.py`.
3. Watch the terminal output. It will reset the board and report:
   ```text
   Connecting........_____.....
   ```
4. **Handling the BOOT Button:**
   - Many ESP32 DevKit boards lack an auto-reset circuit with sufficient capacitance on the `EN` pin to enter the bootloader automatically.
   - If the terminal displays `Connecting........_____.....`, **press and hold the physical "BOOT" (or "IO0") button** on the ESP32 board for 2-3 seconds until the output displays `Chip is ESP32... Writing at 0x00010000...`.
   - Release the button once the percentage progress bar begins advancing.

### Step 7: Identifying a Successful Upload
A successful upload will terminate with output resembling:
```text
Writing at 0x00010000... (100 %)
Wrote 265216 bytes (163820 compressed) at 0x00010000 in 3.8 seconds...
Hash of data verified.

Leaving...
Hard resetting via RTS pin...
```

### Step 8: Serial Monitor Configuration
1. Open the Serial Monitor in Arduino IDE (**Tools -> Serial Monitor** or click the magnifying glass / monitor icon in the upper-right corner).
2. In the Serial Monitor configuration bar (bottom or top right depending on IDE layout):
   - Set the baud rate dropdown to **`115200 baud`**.
   - Set line ending to **`Both NL & CR`** or **`Newline`**.
3. If the board was already running before you opened the monitor, press the physical **"EN" (Enable/Reset)** button on the ESP32 board to restart execution and view the initial banner.

---

## 4. Expected Serial Monitor Output

When the board boots, the following output sequence must appear:

```text
==================================
       FORENSITAP-ESP32
==================================

Hardware initialization: SUCCESS

Chip model: ESP32-D0WD-V3
Chip revision: 3

CPU frequency: 240 MHz

Free heap: 298452 bytes

==================================
System ready.

[HEARTBEAT] ForensiTap ESP32 is running.
[HEARTBEAT] ForensiTap ESP32 is running.
[HEARTBEAT] ForensiTap ESP32 is running.
```
*(Exact chip model, revision number, and byte count for free heap will depend on the physical silicon installed on your specific development board).*

---

## 5. Diagnostic & Troubleshooting Guide

### Issue A: COM Port Does Not Appear in Device Manager
- **Cause:** The USB cable is a charge-only cable, or the USB-to-UART bridge drivers are missing.
- **Solution:**
  1. Test with a different micro-USB cable known to transfer data (e.g., from an Android phone or external drive).
  2. If using a board with a CP2102 chip, download and install the **Silicon Labs CP210x Universal Windows Driver**.
  3. If using a board with a CH340 chip, download and install the **WCH CH340 / CH341 Windows Driver**.

### Issue B: Upload Fails with `A fatal error occurred: Failed to connect to ESP32: Timed out waiting for packet header`
- **Cause:** The ESP32 failed to pull GPIO0 low during reset, preventing entry into the ROM serial download bootloader.
- **Solution:**
  1. Hold down the `BOOT` (or `PRG`/`IO0`) button the moment `Connecting........_____` appears in the IDE.
  2. Release it when `Writing at...` appears.
  3. *(Permanent hardware fix for stubborn boards):* Solder a 10µF electrolytic capacitor between the `EN` pin and `GND`.

### Issue C: Serial Monitor Displays Garbage / Gibberish Characters (`?`)
- **Cause:** Baud rate mismatch between firmware code and terminal software.
- **Solution:** Ensure the Serial Monitor baud rate selector is set strictly to `115200 baud`.

### Issue D: Continuous Reboot / Bootloop (`rst:0x10 (RTCWDT_RTC_RST)`)
- **Cause:** Insufficient power supply or brownout detected by ESP32 internal regulators.
- **Solution:**
  1. Plug the USB cable directly into a motherboard USB 3.0 port rather than an unpowered external USB hub.
  2. Replace degraded cables that cause a voltage drop below 4.5V under peak transmission.
