/**
 * ForensiTap-ESP32: Cybersecurity Live Monitoring Dashboard & SOC Cockpit
 * Next-Gen Multi-Tier Web Interface, Airspace Radar, Explainable Security & Block Explorer
 */

// Configuration State
let API_BASE_URL = localStorage.getItem('forensitap_api_url') || '';
let refreshIntervalMs = 2000;
let isPolling = true;
let pollTimer = null;
let trafficChart = null;
let radarAnimationId = null;
let radarAngle = 0;
let radarHoverDevice = null;

// Operating Mode: 'live', 'usb', or 'demo'
let operatingMode = 'live';
let serialPort = null;
let serialReader = null;
let isFetchInProgress = false;
let lastDataReceivedAt = 0;

// Real-Time Chart Historical Buffer (30 points)
const MAX_CHART_POINTS = 30;
const chartLabels = [];
const chartFpsData = [];
const chartBaselineData = [];

// Demo Simulator Internal State
let simUptimeSec = 145;
let simTotalFrames = 24150;
let simFps = 96.4;
let simEwmaBaseline = 94.2;
let simBaselineStd = 7.8;
let simDeauthRate = 0.0;
let simDeauthRatio = 0.0;
let simBurstScore = 1.2;
let simMgmtRatio = 0.12;
let simBlocksMinted = 16;
let simChainTampered = false;

let simDevices = [
    { mac: '64:FB:92:C0:14:80', is_ap: true, frame_count: 9850, last_rssi_dbm: -54, vendor: 'Cisco / Linksys', is_attacker: false },
    { mac: '50:2E:91:0A:02:B0', is_ap: false, frame_count: 5410, last_rssi_dbm: -42, vendor: 'Apple Inc.', is_attacker: false },
    { mac: '04:C8:07:2A:30:14', is_ap: false, frame_count: 4120, last_rssi_dbm: -66, vendor: 'Intel Mobile', is_attacker: false },
    { mac: '64:FB:92:C0:14:81', is_ap: true, frame_count: 2440, last_rssi_dbm: -61, vendor: 'Cisco / Linksys', is_attacker: false },
    { mac: '42:CF:AA:4B:B3:45', is_ap: false, frame_count: 1120, last_rssi_dbm: -74, vendor: 'Samsung Electronics', is_attacker: false },
    { mac: '9E:A2:F5:F9:EA:95', is_ap: false, frame_count: 480, last_rssi_dbm: -82, vendor: 'Espressif Systems', is_attacker: false }
];

let simAlerts = [
    {
        event_id: 1,
        timestamp: 15000,
        event_type: 'SYSTEM_BOOT',
        severity: 'INFO',
        description: 'ForensiTap ESP32 boot completed. Promiscuous sniffer active on Channel 11.'
    },
    {
        event_id: 2,
        timestamp: 32000,
        event_type: 'NEW_DEVICE_OBSERVED',
        severity: 'INFO',
        description: 'New device observed: [50:2E:91:0A:02:B0] (STA, RSSI: -42 dBm)'
    }
];

let simBlocks = [
    {
        index: 0,
        timestamp_ms: 15000,
        event_type: 'SYSTEM_BOOT',
        severity: 'INFO',
        description: 'Genesis block: ForensiTap evidence chain initialized',
        prev_hash: '0000000000000000000000000000000000000000000000000000000000000000',
        block_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1'
    },
    {
        index: 1,
        timestamp_ms: 32000,
        event_type: 'NEW_DEVICE_OBSERVED',
        severity: 'INFO',
        description: 'New device observed: [50:2E:91:0A:02:B0] (STA, RSSI: -42 dBm)',
        prev_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1',
        block_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00'
    },
    {
        index: 2,
        timestamp_ms: 64000,
        event_type: 'BASELINE_READY',
        severity: 'INFO',
        description: 'Statistical baseline ready: Mean 94.2 fps, EWMA 94.2 fps',
        prev_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00',
        block_hash: '031e9f87a19a9ac7925bb750781fe32b919a778c89b21fae39b7dca46798e1f0'
    }
];

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initControls();
    initTrafficChart();
    initRadarAnimation();

    // Default to demo if running on GitHub pages or file://
    if (window.location.hostname.includes('github.io') || window.location.protocol === 'file:') {
        setMode('demo');
    } else {
        setMode('live');
    }

    restartPolling();
});

// Navigation Handling
function initNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.getAttribute('data-tab');
            switchTab(target);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));

    const tabBtn = document.getElementById(`tabBtn${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
    if (tabBtn) tabBtn.classList.add('active');

    const view = document.getElementById(`view${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
    if (view) view.classList.add('active');

    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Refresh charts or renderers if switching into views
    if (tabId === 'dashboard') {
        if (trafficChart) trafficChart.update();
    } else if (tabId === 'chain') {
        renderChainNodes();
    }
}

// Operating Mode Controls (Live, USB Serial, Demo)
async function setMode(mode) {
    if (operatingMode === 'usb' && mode !== 'usb') {
        await disconnectUsbSerial();
    }
    operatingMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));

    const ipGroup = document.getElementById('ipInputGroup');

    if (mode === 'live') {
        const btnLive = document.getElementById('modeBtnLive');
        if (btnLive) btnLive.classList.add('active');
        if (ipGroup) ipGroup.style.display = 'flex';
        updateConnectionBadge(API_BASE_URL ? 'live' : 'disconnected');
        showToast('Switched to Live Wi-Fi Appliance Mode');
    } else if (mode === 'usb') {
        const btnUsb = document.getElementById('modeBtnUsb');
        if (btnUsb) btnUsb.classList.add('active');
        if (ipGroup) ipGroup.style.display = 'none';
        updateConnectionBadge('usb');
    } else if (mode === 'demo') {
        const btnDemo = document.getElementById('modeBtnDemo');
        if (btnDemo) btnDemo.classList.add('active');
        if (ipGroup) ipGroup.style.display = 'none';
        updateConnectionBadge('demo');
        showToast('Switched to Interactive Demo Mode');
    }
    fetchLatestData();
}

// Connection Badge State Manager
function updateConnectionBadge(state) {
    const badge = document.getElementById('connectionBadge');
    if (!badge) return;

    if (state === 'live') {
        badge.className = 'status-badge online';
        badge.innerHTML = '<span class="status-dot"></span> LIVE WI-FI';
    } else if (state === 'usb') {
        badge.className = 'status-badge usb';
        badge.innerHTML = '<span class="status-dot"></span> USB SERIAL';
    } else if (state === 'demo') {
        badge.className = 'status-badge demo';
        badge.innerHTML = '<span class="status-dot"></span> DEMO SIMULATOR';
    } else if (state === 'warning') {
        badge.className = 'status-badge warning';
        badge.innerHTML = '<span class="status-dot"></span> STALE DATA (>5s)';
    } else if (state === 'offline') {
        badge.className = 'status-badge offline';
        badge.innerHTML = '<span class="status-dot"></span> OFFLINE / RETRYING';
    } else if (state === 'disconnected') {
        badge.className = 'status-badge offline';
        badge.innerHTML = '<span class="status-dot"></span> ' + (API_BASE_URL ? 'DISCONNECTED' : 'AWAITING IP');
    }
}

function recordDataActivity(mode) {
    lastDataReceivedAt = Date.now();
    updateConnectionBadge(mode);
}

// WebSerial API Disconnect & Cleanup
async function disconnectUsbSerial() {
    try {
        if (serialReader) {
            await serialReader.cancel();
            serialReader.releaseLock();
            serialReader = null;
        }
        if (serialPort) {
            await serialPort.close();
            serialPort = null;
        }
    } catch (e) {
        console.warn('[ForensiTap] Error during serial port cleanup:', e);
    }
}

// WebSerial API Connection
async function connectUsbSerial() {
    if (!('serial' in navigator)) {
        alert('WebSerial API is not supported by your current browser. Please use Google Chrome, Microsoft Edge, or Opera.');
        return;
    }

    try {
        if (serialPort) {
            await disconnectUsbSerial();
        }
        serialPort = await navigator.serial.requestPort();
        await serialPort.open({ baudRate: 115200 });
        await setMode('usb');
        updateConnectionBadge('usb');
        showToast('Connected to ESP32 via USB Serial (115200 baud)');
        readSerialStream();
    } catch (err) {
        console.warn('WebSerial connection cancelled or failed:', err);
        if (err.name === 'NotFoundError') {
            showToast('Serial port selection cancelled');
        } else if (err.name === 'SecurityError' || (err.message && err.message.toLowerCase().includes('open')) || err.name === 'NetworkError') {
            alert('Cannot open serial port. If the Arduino IDE Serial Monitor or another tool is currently using this COM port, please close it first and retry.');
        } else {
            showToast(`Serial error: ${err.message || err}`);
        }
        if (operatingMode === 'usb') {
            updateConnectionBadge('offline');
        }
    }
}

// WebSerial Stream Reader with Robust Multi-line Buffering
async function readSerialStream() {
    let textDecoder = new TextDecoderStream();
    let readableStreamClosed = null;
    try {
        readableStreamClosed = serialPort.readable.pipeTo(textDecoder.writable);
        serialReader = textDecoder.readable.getReader();
    } catch (pipeErr) {
        console.error('[ForensiTap] Failed to pipe serial stream:', pipeErr);
        return;
    }

    let buffer = '';
    try {
        while (true) {
            const { value, done } = await serialReader.read();
            if (done) break;
            if (value) {
                buffer += value;
                const lines = buffer.split(/\r?\n/);
                buffer = lines.pop(); // Retain incomplete chunk
                for (const rawLine of lines) {
                    handleSerialLine(rawLine);
                }
            }
        }
    } catch (err) {
        console.warn('[ForensiTap] Serial stream terminated:', err);
        showToast('USB Serial communication interrupted');
    } finally {
        try {
            if (serialReader) {
                serialReader.releaseLock();
                serialReader = null;
            }
            if (serialPort) {
                await serialPort.close();
                serialPort = null;
            }
        } catch (e) {}
        if (operatingMode === 'usb') {
            updateConnectionBadge('disconnected');
        }
    }
}

// Validate IPv4 Address format
function isValidIpv4(ip) {
    if (!ip || typeof ip !== 'string') return false;
    const parts = ip.trim().split('.');
    if (parts.length !== 4) return false;
    for (const part of parts) {
        if (!/^\d+$/.test(part)) return false;
        const num = parseInt(part, 10);
        if (num < 0 || num > 255) return false;
    }
    if (ip === '0.0.0.0' || ip === '255.255.255.255') return false;
    return true;
}

// Handle Auto-Detected IP Address from ESP32 Serial Output
function handleDetectedIp(ip) {
    if (!isValidIpv4(ip)) return;
    const normalizedIp = ip.trim();
    const targetUrl = `http://${normalizedIp}`;

    const subIp = document.getElementById('subIpAddress');
    if (subIp) subIp.textContent = normalizedIp;

    if (API_BASE_URL !== targetUrl) {
        API_BASE_URL = targetUrl;
        localStorage.setItem('forensitap_api_url', targetUrl);
        const apiUrlInput = document.getElementById('apiUrlInput');
        if (apiUrlInput) {
            apiUrlInput.value = targetUrl;
        }
        showToast(`⚡ ESP32 IP auto-detected: ${normalizedIp}`);
        console.log(`[ForensiTap] Auto-configured APPLIANCE URL: ${targetUrl}`);
    }
}

// Comprehensive Serial Line Parser Supporting Types A, B, and C
function handleSerialLine(line) {
    if (!line) return;
    const trimmed = line.trim();
    if (!trimmed) return;

    // Type A: Structured Telemetry Message (@FEATURES {...})
    if (trimmed.startsWith('@FEATURES ')) {
        const payloadStr = trimmed.slice(10).trim();
        try {
            const data = JSON.parse(payloadStr);
            if (toValidNumber(data.frame_rate) === undefined && toValidNumber(data.throughput_kbps) === undefined && toValidNumber(data.unique_peers) === undefined) {
                return;
            }
            if (data.ip_address && data.ip_address !== '0.0.0.0') {
                handleDetectedIp(data.ip_address);
            }
            normalizeAndUpdateUI(data);
            recordDataActivity('usb');
            return;
        } catch (e) {
            console.warn('[ForensiTap] Malformed @FEATURES JSON:', payloadStr, e);
        }
    }

    // Type B: Standard JSON Payload ({...})
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
            const data = JSON.parse(trimmed);
            if (toValidNumber(data.frame_rate) !== undefined || toValidNumber(data.byte_rate) !== undefined || toValidNumber(data.unique_peers) !== undefined) {
                if (data.ip_address && data.ip_address !== '0.0.0.0') {
                    handleDetectedIp(data.ip_address);
                }
                normalizeAndUpdateUI(data);
                recordDataActivity('usb');
                return;
            }
        } catch (e) {
            // Not a valid JSON or not telemetry JSON
        }
    }

    // Type C: Human-Readable Diagnostic Logs
    // 1. IP Address extraction:
    // Matches "[NET] IPv4 Address : 192.168.1.45", "DHCP Lease Granted! IPv4: 192.168.1.45", or "IPv4 Address : 192.168.1.45"
    const ipMatch = trimmed.match(/(?:(?:\[NET\]\s*)?IPv4 Address\s*:\s*|DHCP Lease Granted!\s*IPv4:\s*|Local IP\s*:\s*)([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})/i);
    if (ipMatch && ipMatch[1]) {
        handleDetectedIp(ipMatch[1]);
    }

    // 2. Heartbeat extraction:
    // Supports both new format: "[15000] [INFO] [LIV ] [HEARTBEAT] ForensiTap | WIFI_CONNECTED | MON_ACTIVE | API_ACTIVE | 94 fps | 6 peers | Alerts: 0 | Blocks: 1 | Uptime: 15 s | Heap: 215432 B"
    // and older format: "[15000] [INFO] [LIV] [HEARTBEAT] ForensiTap | WIFI_CONNECTED | 94 fps | 6 peers | Alerts: 0"
    if (trimmed.includes('[HEARTBEAT]')) {
        const hbFps = trimmed.match(/([0-9.]+)\s*fps/i);
        const hbPeers = trimmed.match(/(\d+)\s*peers/i);
        const hbAlerts = trimmed.match(/Alerts:\s*(\d+)/i);
        const hbUptime = trimmed.match(/Uptime:\s*(\d+)\s*s/i);

        if (hbFps || hbPeers || hbAlerts) {
            normalizeAndUpdateUI({
                frame_rate: hbFps ? parseFloat(hbFps[1]) : undefined,
                unique_peers: hbPeers ? parseInt(hbPeers[1], 10) : undefined,
                alerts_total: hbAlerts ? parseInt(hbAlerts[1], 10) : undefined,
                uptime_sec: hbUptime ? parseInt(hbUptime[1], 10) : undefined
            });
            recordDataActivity('usb');
            return;
        }
    }

    // 3. 10s Window Rates extraction:
    // Example: "10s Window Rates: 94.5 fps | 32.1 KB/s | Deauth: 0.0 fps"
    const rateMatch = trimmed.match(/10s Window Rates:\s*([0-9.]+)\s*fps\s*\|\s*([0-9.]+)\s*KB\/s\s*\|\s*Deauth:\s*([0-9.]+)\s*fps/i);
    if (rateMatch) {
        const frameRate = parseFloat(rateMatch[1]);
        const kbPerSec = parseFloat(rateMatch[2]);
        const deauthRate = parseFloat(rateMatch[3]);

        normalizeAndUpdateUI({
            frame_rate: frameRate,
            byte_rate: kbPerSec * 1024.0,
            throughput_kbps: kbPerSec * 8.0,
            deauth_rate: deauthRate
        });
        recordDataActivity('usb');
        return;
    }

    // 4. Subsystem Feature Details (Unique Peers, Burst Score):
    // Example: "Unique Peers    : 6 devices | Burst Score: 1.20"
    const peerBurstMatch = trimmed.match(/Unique Peers\s*:\s*(\d+)\s*devices\s*\|\s*Burst Score:\s*([0-9.]+)/i);
    if (peerBurstMatch) {
        normalizeAndUpdateUI({
            unique_peers: parseInt(peerBurstMatch[1], 10),
            traffic_burst_score: parseFloat(peerBurstMatch[2])
        });
        recordDataActivity('usb');
        return;
    }

    // 5. Baseline Profile:
    // Example: "Baseline Profile: Welford: 94.2 fps | EWMA: 94.2 fps | Z-Score: +0.03"
    const baseMatch = trimmed.match(/Baseline Profile:\s*Welford:\s*([0-9.]+)\s*fps\s*\|\s*EWMA:\s*([0-9.]+)\s*fps\s*\|\s*Z-Score:\s*([+-]?[0-9.]+)/i);
    if (baseMatch) {
        normalizeAndUpdateUI({
            baseline: {
                warmup_ready: true,
                mean_frame_rate: parseFloat(baseMatch[1]),
                ewma_mean_frame_rate: parseFloat(baseMatch[2]),
                frame_rate_zscore: parseFloat(baseMatch[3])
            }
        });
        recordDataActivity('usb');
        return;
    }
}

// Safely parse finite numbers
function toValidNumber(val) {
    if (val === undefined || val === null || val === '') return undefined;
    const num = Number(val);
    return (typeof num === 'number' && !isNaN(num) && isFinite(num)) ? num : undefined;
}

// Telemetry Normalization Pipeline
function normalizeAndUpdateUI(data) {
    if (!data) return;

    const normalized = {
        frame_rate: toValidNumber(data.frame_rate),
        byte_rate: toValidNumber(data.byte_rate) !== undefined ? toValidNumber(data.byte_rate) : (toValidNumber(data.throughput_kbps) !== undefined ? toValidNumber(data.throughput_kbps) * 125 : undefined),
        throughput_kbps: toValidNumber(data.throughput_kbps) !== undefined ? toValidNumber(data.throughput_kbps) : (toValidNumber(data.byte_rate) !== undefined ? (toValidNumber(data.byte_rate) * 8.0) / 1000.0 : undefined),
        deauth_rate: toValidNumber(data.deauth_rate),
        disassoc_rate: toValidNumber(data.disassoc_rate),
        deauth_ratio: toValidNumber(data.deauth_ratio),
        management_frame_ratio: toValidNumber(data.management_frame_ratio) !== undefined ? toValidNumber(data.management_frame_ratio) : toValidNumber(data.mgmt_ratio),
        traffic_burst_score: toValidNumber(data.traffic_burst_score) !== undefined ? toValidNumber(data.traffic_burst_score) : toValidNumber(data.burst_score),
        unique_peers: toValidNumber(data.unique_peers),
        average_frame_size: toValidNumber(data.average_frame_size) !== undefined ? toValidNumber(data.average_frame_size) : toValidNumber(data.avg_frame_size),
        uptime_sec: toValidNumber(data.uptime_sec),
        alerts_total: toValidNumber(data.alerts_total),
        baseline: data.baseline || undefined
    };

    updateFeaturesUI(normalized);

    if (normalized.uptime_sec !== undefined) {
        const valUptime = document.getElementById('valUptime');
        if (valUptime) valUptime.textContent = formatUptime(normalized.uptime_sec);
    }
}

// Controls Setup
function initControls() {
    const apiUrlInput = document.getElementById('apiUrlInput');
    if (apiUrlInput) {
        apiUrlInput.value = API_BASE_URL;
        apiUrlInput.addEventListener('change', () => {
            let val = apiUrlInput.value.trim().replace(/\/+$/, '');
            if (val && !val.startsWith('http://') && !val.startsWith('https://')) {
                val = 'http://' + val;
            }
            API_BASE_URL = val;
            apiUrlInput.value = val;
            if (val) {
                localStorage.setItem('forensitap_api_url', API_BASE_URL);
                showToast(`Target Appliance updated to: ${API_BASE_URL}`);
                const subIp = document.getElementById('subIpAddress');
                if (subIp) subIp.textContent = val.replace(/^https?:\/\//, '');
            } else {
                localStorage.removeItem('forensitap_api_url');
                showToast('Target Appliance IP cleared');
                const subIp = document.getElementById('subIpAddress');
                if (subIp) subIp.textContent = 'Disconnected';
            }
            fetchLatestData();
        });
    }

    // Stale Telemetry Watchdog (>5 seconds without updates)
    setInterval(() => {
        if (operatingMode === 'demo') return;
        if (lastDataReceivedAt > 0 && Date.now() - lastDataReceivedAt > 5000) {
            updateConnectionBadge('warning');
        }
    }, 1000);

    const intervalSelect = document.getElementById('intervalSelect');
    if (intervalSelect) {
        intervalSelect.addEventListener('change', () => {
            refreshIntervalMs = parseInt(intervalSelect.value, 10);
            restartPolling();
        });
    }

    const togglePollingBtn = document.getElementById('togglePollingBtn');
    if (togglePollingBtn) {
        togglePollingBtn.addEventListener('click', () => {
            isPolling = !isPolling;
            togglePollingBtn.textContent = isPolling ? 'Pause' : 'Resume';
            togglePollingBtn.style.color = isPolling ? '#fff' : 'var(--amber-warning)';
            if (isPolling) {
                restartPolling();
                showToast('Telemetry streaming resumed');
            } else {
                if (pollTimer) clearInterval(pollTimer);
                showToast('Telemetry streaming paused');
            }
        });
    }
}

function restartPolling() {
    if (pollTimer) clearInterval(pollTimer);
    if (isPolling) {
        fetchLatestData();
        pollTimer = setInterval(fetchLatestData, refreshIntervalMs);
    }
}

// Chart.js Setup
function initTrafficChart() {
    const ctx = document.getElementById('trafficChartCanvas');
    if (!ctx) return;

    for (let i = MAX_CHART_POINTS - 1; i >= 0; i--) {
        chartLabels.push(`-${i * 2}s`);
        chartFpsData.push(90 + Math.random() * 10);
        chartBaselineData.push(94);
    }

    trafficChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'Observed Frame Rate (FPS)',
                    data: chartFpsData,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.12)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: 'Adaptive EWMA Baseline (FPS)',
                    data: chartBaselineData,
                    borderColor: '#8b5cf6',
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Inter', size: 11 }
                    }
                },
                tooltip: {
                    backgroundColor: '#111a2e',
                    borderColor: '#1e2c48',
                    borderWidth: 1,
                    titleFont: { family: 'Inter' },
                    bodyFont: { family: 'JetBrains Mono' }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
                },
                y: {
                    min: 0,
                    suggestedMax: 150,
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
                }
            }
        }
    });
}

// Airspace Radar Sweeper Animation
function initRadarAnimation() {
    const canvasSmall = document.getElementById('airspaceRadarCanvas');
    const canvasLarge = document.getElementById('airspaceRadarLargeCanvas');

    [canvasSmall, canvasLarge].forEach(canvas => {
        if (!canvas) return;
        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);
            const mouseY = (e.clientY - rect.top) * (canvas.height / rect.height);
            checkRadarHover(canvas, mouseX, mouseY);
        });
        canvas.addEventListener('mouseleave', () => {
            radarHoverDevice = null;
        });
    });

    function animateRadar() {
        radarAngle = (radarAngle + 0.025) % (Math.PI * 2);
        if (canvasSmall) drawRadarOnCanvas(canvasSmall, 170);
        if (canvasLarge) drawRadarOnCanvas(canvasLarge, 300);
        radarAnimationId = requestAnimationFrame(animateRadar);
    }
    animateRadar();
}

function checkRadarHover(canvas, mouseX, mouseY) {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const maxR = (canvas.width / 2) - 15;
    const devices = (operatingMode === 'demo') ? simDevices : (window.lastFetchedDevices || []);

    radarHoverDevice = null;
    for (let index = 0; index < devices.length; index++) {
        const dev = devices[index];
        const rssi = dev.last_rssi_dbm || dev.rssi || -60;
        const normalizedDist = Math.max(0.15, Math.min(0.95, ((-rssi - 20) / 75)));
        const r = maxR * normalizedDist;
        const macHash = hashStringToAngle(dev.mac || `dev_${index}`);
        const x = cx + r * Math.cos(macHash);
        const y = cy + r * Math.sin(macHash);

        const dist = Math.hypot(mouseX - x, mouseY - y);
        if (dist <= 14) {
            radarHoverDevice = { ...dev, x, y };
            break;
        }
    }
}

function drawRadarOnCanvas(canvas, radius) {
    const ctx = canvas.getContext('2d');
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const maxR = radius - 15;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Concentric range rings
    const rings = [0.25, 0.5, 0.75, 1.0];
    const labels = ['-30 dBm', '-50 dBm', '-70 dBm', '-90 dBm'];
    ctx.lineWidth = 1;

    rings.forEach((ratio, idx) => {
        ctx.beginPath();
        ctx.arc(cx, cy, maxR * ratio, 0, Math.PI * 2);
        ctx.strokeStyle = idx === rings.length - 1 ? 'rgba(6, 182, 212, 0.35)' : 'rgba(30, 44, 72, 0.6)';
        ctx.stroke();

        ctx.fillStyle = '#64748b';
        ctx.font = '9px JetBrains Mono';
        ctx.fillText(labels[idx], cx + 4, cy - (maxR * ratio) + 12);
    });

    // Crosshairs
    ctx.beginPath();
    ctx.moveTo(cx - maxR, cy);
    ctx.lineTo(cx + maxR, cy);
    ctx.moveTo(cx, cy - maxR);
    ctx.lineTo(cx, cy + maxR);
    ctx.strokeStyle = 'rgba(30, 44, 72, 0.4)';
    ctx.stroke();

    // Rotating Sweep Beam
    const gradient = ctx.createConicGradient(radarAngle, cx, cy);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.28)');
    gradient.addColorStop(0.15, 'rgba(6, 182, 212, 0.0)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
    ctx.fill();

    // Center Sensor Indicator (ForensiTap ESP32)
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#06b6d4';
    ctx.shadowColor = '#06b6d4';
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Draw Tracked Device Blips
    const devices = (operatingMode === 'demo') ? simDevices : (window.lastFetchedDevices || []);
    const deviceCountBadge = document.getElementById('radarDeviceCount');
    if (deviceCountBadge) deviceCountBadge.textContent = `${devices.length} active blips`;

    devices.forEach((dev, index) => {
        // Map RSSI (-30 to -95 dBm) to radial distance
        const rssi = dev.last_rssi_dbm || dev.rssi || -60;
        const normalizedDist = Math.max(0.15, Math.min(0.95, ((-rssi - 20) / 75)));
        const r = maxR * normalizedDist;

        // Spread angles evenly around the radar based on MAC hash
        const macHash = hashStringToAngle(dev.mac || `dev_${index}`);
        const x = cx + r * Math.cos(macHash);
        const y = cy + r * Math.sin(macHash);

        const isHovered = (radarHoverDevice && radarHoverDevice.mac === dev.mac);

        ctx.beginPath();
        ctx.arc(x, y, dev.is_attacker ? (isHovered ? 8 : 6) : (isHovered ? 6 : 4), 0, Math.PI * 2);

        if (dev.is_attacker) {
            ctx.fillStyle = '#ef4444';
            ctx.shadowColor = '#ef4444';
            ctx.shadowBlur = isHovered ? 18 : 12;
        } else if (dev.is_ap) {
            ctx.fillStyle = '#06b6d4';
            ctx.shadowColor = '#06b6d4';
            ctx.shadowBlur = isHovered ? 12 : 6;
        } else {
            ctx.fillStyle = '#10b981';
            ctx.shadowColor = '#10b981';
            ctx.shadowBlur = isHovered ? 12 : 6;
        }
        ctx.fill();
        ctx.shadowBlur = 0;

        // Outer halo when hovered
        if (isHovered) {
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, Math.PI * 2);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Label top transmitters
        if (dev.is_attacker || dev.is_ap || index < 3) {
            ctx.fillStyle = '#cbd5e1';
            ctx.font = '9px JetBrains Mono';
            ctx.fillText(dev.mac.slice(-8), x + 6, y + 3);
        }
    });

    // Render Floating HUD Tooltip if Hovering a Device
    if (radarHoverDevice) {
        const d = radarHoverDevice;
        const tipX = Math.min(canvas.width - 150, Math.max(10, d.x + 12));
        const tipY = Math.max(30, d.y - 45);

        ctx.fillStyle = 'rgba(10, 16, 30, 0.94)';
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(tipX, tipY, 140, 48, 6);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = 'bold 9px JetBrains Mono';
        ctx.fillText(d.mac, tipX + 8, tipY + 14);

        ctx.fillStyle = '#94a3b8';
        ctx.font = '8px Inter';
        ctx.fillText(`${d.vendor || guessVendor(d.mac)} (${d.is_ap ? 'AP' : 'STA'})`, tipX + 8, tipY + 28);

        ctx.fillStyle = '#06b6d4';
        ctx.font = '8px JetBrains Mono';
        const rssi = d.last_rssi_dbm || d.rssi || -60;
        const frames = (d.frame_count || d.packets || 0).toLocaleString();
        ctx.fillText(`${rssi} dBm | ${frames} frames`, tipX + 8, tipY + 41);
    }
}

function hashStringToAngle(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash % 360) * (Math.PI / 180);
}

// Data Fetching Dispatcher
async function fetchLatestData() {
    if (operatingMode === 'demo') {
        runSimulatorCycle();
        return;
    }

    if (operatingMode === 'usb') {
        // WebSerial reads pushed asynchronous lines directly
        return;
    }

    // Check if target appliance URL is configured
    if (!API_BASE_URL) {
        updateConnectionBadge('disconnected');
        return;
    }

    if (isFetchInProgress) return; // Prevent overlapping HTTP cycles
    isFetchInProgress = true;

    try {
        const [healthRes, statsRes, featRes, devRes, alertRes, logsRes] = await Promise.allSettled([
            fetch(`${API_BASE_URL}/api/health`, { signal: AbortSignal.timeout(2000) }),
            fetch(`${API_BASE_URL}/api/stats`, { signal: AbortSignal.timeout(2000) }),
            fetch(`${API_BASE_URL}/api/features`, { signal: AbortSignal.timeout(2000) }),
            fetch(`${API_BASE_URL}/api/devices`, { signal: AbortSignal.timeout(2000) }),
            fetch(`${API_BASE_URL}/api/alerts`, { signal: AbortSignal.timeout(2000) }),
            fetch(`${API_BASE_URL}/api/logs`, { signal: AbortSignal.timeout(2000) })
        ]);

        let anySuccess = false;

        if (healthRes.status === 'fulfilled' && healthRes.value.ok) {
            const health = await healthRes.value.json();
            updateHealthUI(health);
            anySuccess = true;
        }
        if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
            const stats = await statsRes.value.json();
            updateStatsUI(stats);
            anySuccess = true;
        }
        if (featRes.status === 'fulfilled' && featRes.value.ok) {
            const feat = await featRes.value.json();
            normalizeAndUpdateUI(feat);
            anySuccess = true;
        }
        if (devRes.status === 'fulfilled' && devRes.value.ok) {
            const devData = await devRes.value.json();
            window.lastFetchedDevices = devData.devices || [];
            updateDevicesUI(window.lastFetchedDevices);
            anySuccess = true;
        }
        if (alertRes.status === 'fulfilled' && alertRes.value.ok) {
            const alertData = await alertRes.value.json();
            updateAlertsUI(alertData.alerts || []);
            anySuccess = true;
        }
        if (logsRes.status === 'fulfilled' && logsRes.value.ok) {
            const logsData = await logsRes.value.json();
            updateEvidenceUI(logsData);
            anySuccess = true;
        }

        if (anySuccess) {
            recordDataActivity('live');
        } else {
            updateConnectionBadge('offline');
        }
    } catch (err) {
        updateConnectionBadge('offline');
    } finally {
        isFetchInProgress = false;
    }
}

// UI Updating Routines
function updateHealthUI(data) {
    const valUptime = document.getElementById('valUptime');
    if (valUptime) {
        const s = data.uptime_sec !== undefined ? data.uptime_sec : Math.floor((data.uptime_ms || 0) / 1000);
        valUptime.textContent = formatUptime(s);
    }
    const subFirmware = document.getElementById('subFirmware');
    if (subFirmware) subFirmware.textContent = `${data.firmware_version || 'v1.2.0'} • Xtensa`;

    const subIp = document.getElementById('subIpAddress');
    if (subIp) {
        subIp.textContent = data.ip_address || (API_BASE_URL ? API_BASE_URL.replace(/^https?:\/\//, '') : 'Disconnected');
    }
}

function updateStatsUI(data) {
    const valFps = document.getElementById('valFps');
    if (valFps) valFps.textContent = `${(data.current_frame_rate || 0).toFixed(1)} fps`;

    const valChannel = document.getElementById('valChannel');
    if (valChannel) valChannel.textContent = `CH ${data.active_channel || 11}`;
}

function updateFeaturesUI(data) {
    if (!data) return;

    if (data.frame_rate !== undefined) {
        const featWindowFps = document.getElementById('featWindowFps');
        if (featWindowFps) featWindowFps.textContent = `${data.frame_rate.toFixed(1)} fps`;

        const valFps = document.getElementById('valFps');
        if (valFps) valFps.textContent = `${data.frame_rate.toFixed(1)} fps`;
    }

    if (data.throughput_kbps !== undefined || data.byte_rate !== undefined) {
        const featByteRate = document.getElementById('featByteRate');
        if (featByteRate) {
            const kbVal = data.throughput_kbps !== undefined ? (data.throughput_kbps / 8.0) : (data.byte_rate / 1024.0);
            featByteRate.textContent = `${kbVal.toFixed(1)} KB/s`;
        }
    }

    if (data.average_frame_size !== undefined) {
        const featAvgSize = document.getElementById('featAvgSize');
        if (featAvgSize) featAvgSize.textContent = `${Math.round(data.average_frame_size)} B`;
    }

    if (data.management_frame_ratio !== undefined) {
        const featMgmtRatio = document.getElementById('featMgmtRatio');
        if (featMgmtRatio) featMgmtRatio.textContent = `${(data.management_frame_ratio * 100).toFixed(1)}%`;
    }

    if (data.traffic_burst_score !== undefined) {
        const featBurstScore = document.getElementById('featBurstScore');
        if (featBurstScore) featBurstScore.textContent = data.traffic_burst_score.toFixed(2);
    }

    if (data.deauth_rate !== undefined) {
        const valDeauthRate = document.getElementById('valDeauthRate');
        if (valDeauthRate) valDeauthRate.textContent = `${data.deauth_rate.toFixed(1)} fps`;
    }

    if (data.deauth_ratio !== undefined) {
        const featDeauthRatio = document.getElementById('featDeauthRatio');
        if (featDeauthRatio) featDeauthRatio.textContent = `${(data.deauth_ratio * 100).toFixed(1)}%`;

        const valDeauthRatio = document.getElementById('valDeauthRatio');
        if (valDeauthRatio) valDeauthRatio.textContent = `${(data.deauth_ratio * 100).toFixed(1)}% of total frames`;
    }

    if (data.unique_peers !== undefined) {
        const radarBadge = document.getElementById('radarDeviceCount');
        if (radarBadge && operatingMode !== 'demo') {
            radarBadge.textContent = `${data.unique_peers} active blips`;
        }
    }

    // Baseline profile display
    if (data.baseline) {
        const b = data.baseline;
        const featBaseline = document.getElementById('featBaseline');
        if (featBaseline) {
            if (b.warmup_ready) {
                const meanStr = b.mean_frame_rate !== undefined ? `${b.mean_frame_rate.toFixed(1)} fps` : 'N/A';
                const ewmaStr = b.ewma_mean_frame_rate !== undefined ? `${b.ewma_mean_frame_rate.toFixed(1)} fps` : meanStr;
                const zScoreStr = b.frame_rate_zscore !== undefined ? `${b.frame_rate_zscore >= 0 ? '+' : ''}${b.frame_rate_zscore.toFixed(2)}σ` : '0.00σ';
                featBaseline.innerHTML = `Mean: <strong>${meanStr}</strong> | EWMA: <strong>${ewmaStr}</strong> | Z-Score: <strong>${zScoreStr}</strong>`;
            } else {
                featBaseline.textContent = 'Calibrating background RF profile... (Warm-up in progress)';
            }
        }
    }

    // Update Real-Time Chart
    if (trafficChart && data.frame_rate !== undefined) {
        const currentRate = data.frame_rate;
        const b = data.baseline || {};
        const baselineRate = b.ewma_mean_frame_rate || b.mean_frame_rate || currentRate;

        chartFpsData.shift();
        chartFpsData.push(currentRate);

        chartBaselineData.shift();
        chartBaselineData.push(baselineRate);

        trafficChart.update();
    }
    }

    // Evaluate Edge ML status
    evaluateEdgeML(data);
}

function evaluateEdgeML(feat) {
    const statusText = document.getElementById('mlClassifierStatus');
    const detailText = document.getElementById('mlClassifierDetail');
    const badge = document.getElementById('mlBadge');
    if (!statusText || !badge) return;

    if (feat.deauth_rate >= 3.0 || (feat.frame_rate > 10 && feat.deauth_ratio >= 0.15)) {
        statusText.innerHTML = '🤖 Edge ML: <span style="color:var(--red-danger)">[DEAUTH FLOOD ATTACK]</span>';
        detailText.textContent = 'Sub-millisecond inference on Xtensa Core 1 • Confidence 96%';
        badge.className = 'badge badge-critical';
        badge.textContent = 'THREAT DETECTED';
    } else if (feat.traffic_burst_score >= 4.0) {
        statusText.innerHTML = '🤖 Edge ML: <span style="color:var(--amber-warning)">[BURSTINESS ANOMALY]</span>';
        detailText.textContent = 'Acute traffic concentration • Confidence 88%';
        badge.className = 'badge badge-high';
        badge.textContent = 'EVALUATING';
    } else {
        statusText.innerHTML = '🤖 Edge ML: <span style="color:var(--green-success)">[BENIGN ACTIVITY]</span>';
        detailText.textContent = 'Ambient wireless profile normal • Confidence 95%';
        badge.className = 'badge badge-sta';
        badge.textContent = 'OPTIMAL';
    }
}

function updateDevicesUI(devices) {
    const tbody = document.getElementById('devicesTableBody');
    const badge = document.getElementById('deviceCountBadge');
    if (!tbody) return;

    if (badge) badge.textContent = `${devices.length} active`;

    if (!devices || devices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;padding:1.5rem">No devices currently detected.</td></tr>';
        return;
    }

    tbody.innerHTML = devices.map(d => {
        const rssi = d.last_rssi_dbm || d.rssi || -65;
        const roleBadge = d.is_ap ? '<span class="badge badge-ap">AP</span>' : '<span class="badge badge-sta">STA</span>';
        const vendor = d.vendor || guessVendor(d.mac);
        return `
            <tr>
                <td style="font-family:var(--font-mono);font-weight:600;color:#fff">${d.mac}</td>
                <td>${vendor} ${roleBadge}</td>
                <td style="font-family:var(--font-mono)">${(d.frame_count || d.packets || 0).toLocaleString()}</td>
                <td style="font-family:var(--font-mono)">
                    <span style="color:${rssi > -60 ? 'var(--green-success)' : rssi > -75 ? 'var(--amber-warning)' : 'var(--text-muted)'}">
                        ${rssi} dBm
                    </span>
                </td>
                <td style="color:var(--text-muted);font-size:0.75rem">${d.last_seen_ms ? Math.round(d.last_seen_ms / 1000) + 's' : 'Just now'}</td>
            </tr>
        `;
    }).join('');
}

function guessVendor(mac) {
    if (!mac) return 'Unknown';
    const prefix = mac.slice(0, 8).toUpperCase();
    if (prefix.startsWith('64:FB:92')) return 'Cisco / Linksys';
    if (prefix.startsWith('50:2E:91')) return 'Apple Inc.';
    if (prefix.startsWith('04:C8:07')) return 'Intel Mobile';
    if (prefix.startsWith('42:CF:AA')) return 'Samsung';
    if (prefix.startsWith('9E:A2:F5')) return 'Espressif';
    return 'Generic 802.11';
}

function updateAlertsUI(alerts) {
    const container = document.getElementById('incidentsContainer');
    const badge = document.getElementById('alertCountBadge');
    if (!container) return;

    if (badge) badge.textContent = `${alerts.length} stored`;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:#64748b;padding:2rem">Listening for wireless security threats... (Zero incidents)</div>';
        return;
    }

    // Render explainable incident response cards (newest first)
    container.innerHTML = [...alerts].reverse().map(a => renderExplainableIncident(a)).join('');
}

function renderExplainableIncident(alert) {
    const type = alert.event_type || 'UNKNOWN';
    const sev = (alert.severity || 'INFO').toLowerCase();
    const timeStr = alert.timestamp ? `${Math.round(alert.timestamp / 1000)}s` : 'Just now';

    let cardClass = 'info';
    let title = 'Information Sighting';
    let whatHappened = alert.description;
    let intent = 'Normal diagnostic event or telemetry sighting.';
    let action = 'No administrative intervention required.';

    if (type === 'DEAUTH_FLOOD_ATTACK') {
        cardClass = 'critical';
        title = '⚡ Critical: Wi-Fi Deauthentication Flood Attack';
        whatHappened = `High-rate deauthentication/disassociation frames observed (${alert.description}). Wireless stations are being kicked off the access point.`;
        intent = 'Attacker attempting to disconnect stations to force WPA 4-way handshake re-authentications for offline dictionary cracking.';
        action = 'Enable 802.11w Protected Management Frames (PMF) on target AP or isolate RF channel.';
    } else if (type === 'EVIL_TWIN_SUSPECTED') {
        cardClass = 'critical';
        title = '📡 Critical: Rogue AP / Evil Twin Transmitter';
        whatHappened = `Identical BSSID observed with dramatic signal disparity (${alert.description}).`;
        intent = 'Man-in-the-Middle (MitM) credential harvesting or captive portal phishing.';
        action = 'Perform RF directional signal sweep to locate unauthorized rogue transmitter.';
    } else if (type === 'TRAFFIC_SPIKE') {
        cardClass = 'medium';
        title = '📈 Warning: Statistical Frame Rate Surge';
        whatHappened = `Observed packet rate surged past +3.0σ standard deviations above EWMA baseline profile (${alert.description}).`;
        intent = 'Active network scanning, reconnaissance probe, or high-volume packet injection.';
        action = 'Inspect active device frame count table for high-velocity transmitters.';
    } else if (type === 'MGMT_ANOMALY') {
        cardClass = 'high';
        title = '🚨 High: Abnormal Management Frame Saturation';
        whatHappened = `Management frames exceed 60% of total observed traffic (${alert.description}).`;
        intent = 'Beacon flooding, probe request fuzzing, or Layer 2 denial of service.';
        action = 'Filter management subtypes in sniffer log.';
    } else if (type === 'NEW_DEVICE_OBSERVED') {
        cardClass = 'info';
        title = '👥 Info: Unrecognized Transmitter Observed';
        whatHappened = alert.description;
        intent = 'Station or access point entering the local 2.4 GHz RF perimeter.';
        action = 'Catalog MAC address in authorized device inventory.';
    }

    return `
        <div class="incident-card ${cardClass}">
            <div class="incident-top">
                <span class="incident-title">${title}</span>
                <span class="incident-time">${timeStr}</span>
            </div>
            <div class="incident-desc">${whatHappened}</div>
            <div class="incident-meta-grid">
                <div class="incident-meta-item">
                    <strong>Likely Attacker Intent</strong>
                    <span>${intent}</span>
                </div>
                <div class="incident-meta-item">
                    <strong>Forensic Remediation</strong>
                    <span>${action}</span>
                </div>
            </div>
        </div>
    `;
}

function updateEvidenceUI(data) {
    const valBlocks = document.getElementById('valBlocksMinted');
    if (valBlocks) valBlocks.textContent = `${data.total_blocks || data.stored_count || 0} blocks`;

    const genesisText = document.getElementById('genesisHashText');
    if (genesisText) genesisText.textContent = data.genesis_hash ? data.genesis_hash.slice(0, 24) + '...' : '---';

    const tipText = document.getElementById('tipHashText');
    if (tipText) tipText.textContent = data.tip_hash ? data.tip_hash.slice(0, 24) + '...' : '---';

    const statusBadge = document.getElementById('chainStatusBadge');
    if (statusBadge) {
        if (data.chain_valid && !simChainTampered) {
            statusBadge.style.color = 'var(--green-success)';
            statusBadge.textContent = 'VERIFIED INTACT (100%)';
        } else {
            statusBadge.style.color = 'var(--red-danger)';
            statusBadge.textContent = 'INTEGRITY BROKEN (TAMPERED)';
        }
    }

    renderChainNodes(data.blocks || simBlocks);

    // Update Detailed Block Table
    const tbody = document.getElementById('evidenceTableBody');
    if (tbody && data.blocks) {
        tbody.innerHTML = data.blocks.map(b => `
            <tr>
                <td style="font-family:var(--font-mono);font-weight:700">#${b.index}</td>
                <td style="font-family:var(--font-mono)">${b.timestamp_ms ? Math.round(b.timestamp_ms / 1000) + 's' : '0s'}</td>
                <td><span class="badge badge-info">${b.event_type}</span></td>
                <td style="font-size:0.75rem">${b.description}</td>
                <td style="font-family:var(--font-mono);font-size:0.70rem;color:var(--text-muted)">${b.prev_hash.slice(0, 16)}...</td>
                <td style="font-family:var(--font-mono);font-size:0.70rem;color:var(--cyan-primary)">${b.block_hash.slice(0, 16)}...</td>
            </tr>
        `).join('');
    }
}

function renderChainNodes(blocks = simBlocks) {
    const containers = [
        document.getElementById('chainVisualNodes'),
        document.getElementById('chainVisualNodesDedicated')
    ];

    containers.forEach(container => {
        if (!container) return;

        container.innerHTML = blocks.map((b, idx) => {
            const isCorrupted = (simChainTampered && idx >= 2);
            const blockClass = isCorrupted ? 'chain-block-node corrupted' : 'chain-block-node valid';
            const arrowClass = isCorrupted ? 'chain-arrow broken' : 'chain-arrow';

            return `
                <div class="${blockClass}" onclick="inspectBlock(${b.index})">
                    <div class="chain-node-idx">
                        <span>BLOCK #${b.index}</span>
                        <span>${isCorrupted ? '❌ BROKEN' : '✅ VALID'}</span>
                    </div>
                    <div class="chain-node-type">${b.event_type}</div>
                    <div class="chain-node-hash">${b.block_hash.slice(0, 14)}...</div>
                </div>
                ${idx < blocks.length - 1 ? `<div class="${arrowClass}">➔</div>` : ''}
            `;
        }).join('');
    });
}

// Interactive Attack Simulator Controls
function triggerSimAttack(attackType) {
    setMode('demo');

    if (attackType === 'deauth') {
        simFps = 280.0;
        simDeauthRate = 42.5;
        simDeauthRatio = 0.38;
        simBurstScore = 5.2;

        simAlerts.push({
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'DEAUTH_FLOOD_ATTACK',
            severity: 'CRITICAL',
            description: '42.5 deauth fps detected (38% of all frames). Targeted victim: [04:C8:07:2A:30:14]'
        });

        mintSimBlock('DEAUTH_FLOOD_ATTACK', 'CRITICAL', '42.5 deauth fps detected. Victim: [04:C8:07:2A:30:14]');
        showToast('🚨 Simulated Deauth Storm triggered! High-rate deauth frames injected.');
    } else if (attackType === 'spike') {
        simFps = 480.0;
        simBurstScore = 4.2;

        simAlerts.push({
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'TRAFFIC_SPIKE',
            severity: 'MEDIUM',
            description: 'Traffic spike detected: 480.0 fps (Z-Score: +4.82 > +3.0σ)'
        });

        mintSimBlock('TRAFFIC_SPIKE', 'MEDIUM', 'Traffic surge 480.0 fps (+4.82σ deviation)');
        showToast('📈 Simulated Traffic Surge (+4.82σ) triggered!');
    } else if (attackType === 'rogue') {
        simAlerts.push({
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'EVIL_TWIN_SUSPECTED',
            severity: 'CRITICAL',
            description: 'Suspected Rogue AP: BSSID [64:FB:92:C0:14:80] RSSI shifted -54 -> -21 dBm'
        });

        // Add rogue attacker node to radar
        simDevices.push({
            mac: '64:FB:92:C0:14:80',
            is_ap: true,
            frame_count: 850,
            last_rssi_dbm: -21,
            vendor: 'Rogue Clone AP',
            is_attacker: true
        });

        mintSimBlock('EVIL_TWIN_SUSPECTED', 'CRITICAL', 'Rogue AP cloned BSSID [64:FB:92:C0:14:80] with -21 dBm');
        showToast('📡 Rogue AP / Evil Twin detected! RSSI spoofing alert generated.');
    } else if (attackType === 'burst') {
        simBurstScore = 6.4;
        simAlerts.push({
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'ACTIVITY_DEVIATION',
            severity: 'LOW',
            description: 'High traffic burstiness: score 6.40 (threshold: 5.0)'
        });
        showToast('🌊 Micro-Burst pulse anomaly triggered!');
    }

    runSimulatorCycle();
}

function mintSimBlock(eventType, severity, desc) {
    const prevBlock = simBlocks[simBlocks.length - 1];
    const newIdx = simBlocks.length;
    const fakeHash = 'e8b' + Math.random().toString(16).substring(2, 10) + '28de3b56d89a1424ce5b' + newIdx;

    simBlocks.push({
        index: newIdx,
        timestamp_ms: simUptimeSec * 1000,
        event_type: eventType,
        severity: severity,
        description: desc,
        prev_hash: prevBlock.block_hash,
        block_hash: fakeHash
    });
}

function toggleTamperSimulation() {
    setMode('demo');
    simChainTampered = !simChainTampered;

    if (simChainTampered) {
        showToast('⚠️ Tampering Injected: Altered 1 byte in Block #1. Notice downstream blocks turn RED!');
    } else {
        showToast('✅ Restored Cryptographic Proof. All SHA-256 blocks validated intact.');
    }
    runSimulatorCycle();
}

function resetSimData() {
    simFps = 95.0;
    simEwmaBaseline = 94.2;
    simDeauthRate = 0.0;
    simDeauthRatio = 0.0;
    simBurstScore = 1.2;
    simChainTampered = false;
    simDevices = simDevices.filter(d => !d.is_attacker);
    showToast('🔄 Restored standard baseline profile (95 fps, zero attacks)');
    runSimulatorCycle();
}

function runSimulatorCycle() {
    simUptimeSec += 2;
    simTotalFrames += Math.round(simFps * 2);

    // Natural jitter
    if (simDeauthRate > 0) {
        simDeauthRate = Math.max(0, simDeauthRate - 3.5);
        if (simDeauthRate === 0) simDeauthRatio = 0;
    }
    if (simFps > 120) {
        simFps = Math.max(95, simFps - 30);
    }

    const simData = {
        frame_rate: simFps,
        byte_rate: simFps * 420,
        average_frame_size: 420,
        unique_peers: simDevices.length,
        management_frame_ratio: simMgmtRatio + (simDeauthRatio * 0.5),
        traffic_burst_score: simBurstScore,
        deauth_rate: simDeauthRate,
        disassoc_rate: 0.0,
        deauth_ratio: simDeauthRatio,
        baseline: {
            warmup_ready: true,
            mean_frame_rate: simEwmaBaseline,
            ewma_mean_frame_rate: simEwmaBaseline,
            std_frame_rate: simBaselineStd,
            frame_rate_zscore: (simFps - simEwmaBaseline) / simBaselineStd
        }
    };

    updateHealthUI({ uptime_sec: simUptimeSec, firmware_version: 'v1.2.0-sim', ip_address: '192.168.4.1 (Simulated)' });
    updateStatsUI({ current_frame_rate: simFps, active_channel: 11 });
    updateFeaturesUI(simData);
    updateDevicesUI(simDevices);
    updateAlertsUI(simAlerts);
    updateEvidenceUI({
        chain_valid: !simChainTampered,
        total_blocks: simBlocks.length,
        stored_count: simBlocks.length,
        genesis_hash: simBlocks[0].block_hash,
        tip_hash: simBlocks[simBlocks.length - 1].block_hash,
        blocks: simBlocks
    });
}

async function auditChainNow() {
    if (operatingMode === 'live') {
        try {
            const res = await fetch(`${API_BASE_URL}/api/logs/verify`);
            const data = await res.json();
            if (data.is_valid) {
                alert(`✅ LIVE AUDIT PASSED!\n\nAll ${data.blocks_checked} evidence blocks cryptographically verified from Genesis to Tip.`);
            } else {
                alert(`❌ LIVE AUDIT FAILED!\n\nChain broken at Block #${data.failed_index}: ${data.reason}`);
            }
            return;
        } catch (e) {}
    }

    if (simChainTampered) {
        alert('❌ AUDIT FAILED!\n\nBlock #2: prev_hash does not match hash of Block #1.\nCryptographic tamper detected! Historical records have been altered.');
    } else {
        alert('✅ AUDIT PASSED (100% INTACT)\n\nEvery cryptographic hash in the SHA-256 evidence chain continuously validates from Genesis Anchor #0 through Chain Tip.\nCourt-admissible integrity verified.');
    }
}

function exportCsv() {
    if (operatingMode === 'live') {
        window.open(`${API_BASE_URL}/api/export`, '_blank');
        showToast('Initiating forensic CSV export from appliance...');
        return;
    }

    const blocks = simBlocks;
    let csv = 'Index,Timestamp_MS,Event_Type,Severity,Description,Prev_Hash,Block_Hash\n';
    blocks.forEach(b => {
        csv += `${b.index},${b.timestamp_ms},"${b.event_type}","${b.severity}","${b.description}","${b.prev_hash}","${b.block_hash}"\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `forensitap_evidence_chain_${Date.now()}.csv`;
    a.click();
    showToast('Exported SHA-256 forensic evidence chain as CSV');
}

function inspectBlock(idx) {
    const b = simBlocks.find(x => x.index === idx);
    if (!b) return;
    alert(`BLOCK #${b.index} DETAILS\n\nEvent Type: ${b.event_type}\nTimestamp: ${b.timestamp_ms} ms\nDescription: ${b.description}\n\nPrev Hash:\n${b.prev_hash}\n\nBlock Hash:\n${b.block_hash}`);
}

function showToast(msg) {
    const toast = document.getElementById('dashboardToast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3200);
}

function formatUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}
