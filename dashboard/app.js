/**
 * ForensiTap-ESP32: Cybersecurity Live Monitoring Dashboard & Simulator Client
 * Stage 13 & GitHub Pages Multi-Tier Presentation Implementation
 */

// Configuration State
let API_BASE_URL = localStorage.getItem('forensitap_api_url') || 'http://192.168.1.26';
let refreshIntervalMs = 2000;
let isPolling = true;
let pollTimer = null;
let trafficChart = null;

// Operating Mode: 'live' or 'demo'
let operatingMode = 'live'; // attempts live first, switches to demo on failure if desired

// Real-Time Chart Historical Buffer (30 points)
const MAX_CHART_POINTS = 30;
const chartLabels = [];
const chartFpsData = [];
const chartBaselineData = [];

// Demo Simulator Internal State
let simUptimeSec = 120;
let simTotalFrames = 18450;
let simFps = 95.0;
let simBaselineMean = 92.4;
let simBaselineStd = 8.1;
let simBlocksMinted = 14;
let simChainTampered = false;

let simDevices = [
    { mac: '64:FB:92:C0:14:80', is_ap: true, packets: 7850, rssi: -58, last_seen_ms: 120000 },
    { mac: '50:2E:91:0A:02:B0', is_ap: false, packets: 4210, rssi: -42, last_seen_ms: 119500 },
    { mac: '04:C8:07:2A:30:14', is_ap: false, packets: 3410, rssi: -66, last_seen_ms: 118200 },
    { mac: '64:FB:92:C0:14:81', is_ap: true, packets: 1840, rssi: -61, last_seen_ms: 117000 },
    { mac: '42:CF:AA:4B:B3:45', is_ap: false, packets: 820, rssi: -72, last_seen_ms: 115000 },
    { mac: '9E:A2:F5:F9:EA:95', is_ap: false, packets: 320, rssi: -79, last_seen_ms: 110000 }
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
        event_type: 'GENESIS_ANCHOR',
        description: 'Genesis anchor created for ForensiTap firmware v1.0.0',
        prev_hash: '0000000000000000000000000000000000000000000000000000000000000000',
        block_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1'
    },
    {
        index: 1,
        timestamp_ms: 32000,
        event_type: 'NEW_DEVICE_OBSERVED',
        description: 'New device observed: [50:2E:91:0A:02:B0] (STA, RSSI: -42 dBm)',
        prev_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1',
        block_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00'
    },
    {
        index: 2,
        timestamp_ms: 64000,
        event_type: 'BASELINE_READY',
        description: 'Statistical baseline ready: Mean 92.4 fps, StdDev 8.1 fps',
        prev_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00',
        block_hash: '031e9f87a19a9ac7925bb750781fe32b919a778c89b21fae39b7dca46798e1f0'
    }
];

// Initialize Dashboard & Navigation
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initControls();
    initTrafficChart();

    // Check if we are running from file:// or public github pages without local host
    if (window.location.hostname.includes('github.io') || window.location.protocol === 'file:') {
        setMode('demo');
    } else {
        setMode('live');
    }

    restartPolling();
});

// Tab Switching Navigation
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
    document.querySelectorAll('.nav-tab').forEach(t => {
        if (t.getAttribute('data-tab') === tabId) {
            t.classList.add('active');
        } else {
            t.classList.remove('active');
        }
    });

    document.querySelectorAll('.view-section').forEach(sec => {
        sec.classList.remove('active');
    });

    const targetSec = document.getElementById(`view${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
    if (targetSec) {
        targetSec.classList.add('active');
    }

    // Resize chart if switching to dashboard
    if (tabId === 'dashboard' && trafficChart) {
        setTimeout(() => trafficChart.resize(), 100);
    }
}

// User Controls Setup
function initControls() {
    const apiInput = document.getElementById('apiUrlInput');
    if (apiInput) {
        apiInput.value = API_BASE_URL;
        apiInput.addEventListener('change', (e) => {
            API_BASE_URL = e.target.value.trim().replace(/\/+$/, "");
            localStorage.setItem('forensitap_api_url', API_BASE_URL);
            showToast(`API target updated to ${API_BASE_URL}`);
            setMode('live');
            fetchTelemetry();
        });
    }

    const intervalSelect = document.getElementById('intervalSelect');
    if (intervalSelect) {
        intervalSelect.addEventListener('change', (e) => {
            refreshIntervalMs = parseInt(e.target.value, 10);
            restartPolling();
        });
    }

    const toggleBtn = document.getElementById('togglePollingBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            isPolling = !isPolling;
            toggleBtn.textContent = isPolling ? 'Pause' : 'Resume';
            toggleBtn.className = isPolling ? 'btn' : 'btn btn-primary';
            if (isPolling) restartPolling();
            else clearInterval(pollTimer);
        });
    }

    const verifyBtn = document.getElementById('auditChainBtn');
    if (verifyBtn) {
        verifyBtn.addEventListener('click', triggerChainAudit);
    }

    const exportCsvBtn = document.getElementById('exportCsvBtn');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', () => {
            if (operatingMode === 'live') {
                window.open(`${API_BASE_URL}/api/export?format=csv`, '_blank');
            } else {
                exportSimCsv();
            }
        });
    }
}

function setMode(mode) {
    operatingMode = mode;
    const btn = document.getElementById('simModeToggleBtn');
    if (btn) {
        if (mode === 'demo') {
            btn.textContent = 'Mode: Demo Simulator (Active)';
            btn.className = 'btn btn-primary';
        } else {
            btn.textContent = 'Mode: Live Hardware (Polling ESP32)';
            btn.className = 'btn';
        }
    }
    fetchTelemetry();
}

function toggleSimMode() {
    if (operatingMode === 'demo') {
        setMode('live');
        showToast('Switched to Live ESP32 Mode. Connecting to appliance...');
    } else {
        setMode('demo');
        showToast('Switched to Interactive Demo Simulator Mode.');
    }
}

function restartPolling() {
    if (pollTimer) clearInterval(pollTimer);
    if (isPolling) {
        pollTimer = setInterval(fetchTelemetry, refreshIntervalMs);
    }
}

// Chart Initialization
function initTrafficChart() {
    const ctx = document.getElementById('trafficChartCanvas');
    if (!ctx) return;

    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not yet loaded from CDN');
        return;
    }

    // Seed initial points
    const now = new Date();
    for (let i = 15; i >= 0; i--) {
        const t = new Date(now.getTime() - i * 2000).toLocaleTimeString();
        chartLabels.push(t);
        chartFpsData.push(Math.round(85 + Math.random() * 20));
        chartBaselineData.push(92.4);
    }

    trafficChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'Observed FPS',
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    data: chartFpsData,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                },
                {
                    label: 'Baseline Mean FPS',
                    borderColor: '#f59e0b',
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    data: chartBaselineData,
                    tension: 0,
                    fill: false,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            scales: {
                x: {
                    grid: { color: '#1e293b' },
                    ticks: { color: '#64748b', font: { family: 'monospace', size: 10 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#1e293b' },
                    ticks: { color: '#94a3b8', font: { family: 'monospace', size: 10 } }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#cbd5e1', font: { size: 11 } }
                }
            }
        }
    });
}

// Main Telemetry Fetch Orchestrator
async function fetchTelemetry() {
    if (operatingMode === 'demo') {
        renderDemoTick();
        return;
    }

    const startTime = performance.now();
    try {
        const [healthRes, statsRes, featRes, devRes, alertRes, logsRes, verifyRes] = await Promise.all([
            fetch(`${API_BASE_URL}/api/health`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/stats`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/features`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/devices`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/alerts`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/logs`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE_URL}/api/logs/verify`, { cache: 'no-store' }).then(r => r.json()).catch(() => null)
        ]);

        const latencyMs = Math.round(performance.now() - startTime);

        if (healthRes) {
            updateConnectionBadge(true, latencyMs, 'LIVE');
            updateHealthCard(healthRes);
            if (statsRes) updateStats(statsRes);
            if (featRes) updateFeatures(featRes);
            if (devRes) updateDevices(devRes);
            if (alertRes) updateAlerts(alertRes);
            if (logsRes && verifyRes) updateEvidenceChain(logsRes, verifyRes);
        } else {
            // Live poll failed; fallback prompt
            updateConnectionBadge(false, 0, 'OFFLINE');
        }

    } catch (err) {
        console.error('Telemetry query error:', err);
        updateConnectionBadge(false, 0, 'OFFLINE');
    }
}

// Demo Simulator Loop
function renderDemoTick() {
    simUptimeSec += Math.round(refreshIntervalMs / 1000);
    
    // Slight random drift
    const delta = (Math.random() - 0.5) * 8;
    simFps = Math.max(25, Math.min(350, simFps + delta));
    simTotalFrames += Math.round(simFps * (refreshIntervalMs / 1000));

    updateConnectionBadge(true, 1, 'SIMULATOR ACTIVE');

    // Health Card
    setText('valUptime', `${simUptimeSec}s`);
    setText('valChannel', `CH 11`);
    setText('valRssi', `-57 dBm`);
    setText('valHeap', `226 KB`);
    setText('subIpAddress', '192.168.1.26 (Sim)');
    setText('subFirmware', 'v1.0.0-stage17-sim');

    // Stats
    const fpsRound = Math.round(simFps);
    setText('valFps', `${fpsRound} fps`);
    setText('valTotalFrames', simTotalFrames.toLocaleString());
    setText('valDropped', '0 dropped');

    // Chart update
    const nowStr = new Date().toLocaleTimeString();
    chartLabels.push(nowStr);
    chartFpsData.push(fpsRound);
    chartBaselineData.push(simBaselineMean);

    if (chartLabels.length > MAX_CHART_POINTS) {
        chartLabels.shift();
        chartFpsData.shift();
        chartBaselineData.shift();
    }
    if (trafficChart) trafficChart.update('none');

    // Features
    const zScore = (simFps - simBaselineMean) / simBaselineStd;
    const mgmtRatio = simFps > 200 ? 0.85 : 0.16;
    const burstScore = simFps > 200 ? 4.2 : 1.45;
    const byteRate = (simFps * 210) / 1024;

    setText('featWindowFps', `${simFps.toFixed(1)} fps`);
    setText('featByteRate', `${byteRate.toFixed(1)} KB/s`);
    setText('featAvgSize', `210 B`);
    setText('featMgmtRatio', `${(mgmtRatio * 100).toFixed(1)}%`);
    setText('featBurstScore', burstScore.toFixed(2));
    setText('featBaseline', `${simBaselineMean.toFixed(1)} ± ${simBaselineStd.toFixed(1)} fps (Z: ${zScore > 0 ? '+' : ''}${zScore.toFixed(2)})`);

    // Devices
    updateDevices({ devices: simDevices });

    // Alerts
    updateAlerts({ alerts: simAlerts });

    // Evidence
    const tipHash = simBlocks[simBlocks.length - 1].block_hash;
    const genesisHash = simBlocks[0].block_hash;
    updateEvidenceChain({
        blocks: simBlocks,
        genesis_hash: genesisHash,
        tip_hash: tipHash
    }, {
        chain_intact: !simChainTampered,
        total_blocks_created: simBlocks.length,
        blocks_checked: simBlocks.length
    });
}

// Simulation Attack Injections
function triggerSimAttack(type) {
    if (operatingMode !== 'demo') {
        setMode('demo');
    }

    if (type === 'deauth') {
        simFps = 280.0;
        const alertObj = {
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'MGMT_ANOMALY',
            severity: 'CRITICAL',
            description: 'Deauthentication / Disassociation flood detected! Mgmt ratio: 86.4% (> 60.0%)'
        };
        simAlerts.push(alertObj);
        mintSimBlock('MGMT_ANOMALY', alertObj.description);
        showToast('⚡ [ATTACK SIMULATED] Deauthentication flood injected! Critical alert raised.');
    } else if (type === 'spike') {
        simFps = 325.0;
        const alertObj = {
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'TRAFFIC_SPIKE',
            severity: 'HIGH',
            description: `Traffic spike anomaly: 325.0 fps (Z-Score: +3.82 > +3.0)`
        };
        simAlerts.push(alertObj);
        mintSimBlock('TRAFFIC_SPIKE', alertObj.description);
        showToast('📈 [ATTACK SIMULATED] Massive traffic rate surge detected (+3.82σ).');
    } else if (type === 'rogue') {
        const rogueMac = 'DE:AD:BE:EF:00:13';
        simDevices.unshift({ mac: rogueMac, is_ap: true, packets: 140, rssi: -38, last_seen_ms: simUptimeSec * 1000 });
        const alertObj = {
            event_id: simAlerts.length + 1,
            timestamp: simUptimeSec * 1000,
            event_type: 'NEW_DEVICE_OBSERVED',
            severity: 'MEDIUM',
            description: `Rogue AP / Unfamiliar transmitter observed: [${rogueMac}] (AP, RSSI: -38 dBm)`
        };
        simAlerts.push(alertObj);
        mintSimBlock('NEW_DEVICE_OBSERVED', alertObj.description);
        showToast('📡 [ROGUE DETECTED] Unfamiliar rogue Access Point broadcast identified.');
    } else if (type === 'tamper') {
        simChainTampered = true;
        // Mutate block 1 hash
        if (simBlocks.length > 1) {
            simBlocks[1].block_hash = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';
        }
        showToast('🔒 [TAMPER INJECTED] Modified Block #1 hash to simulate flash corruption / log tampering.');
        triggerChainAudit();
    }

    renderDemoTick();
}

function mintSimBlock(eventType, desc) {
    const prevBlock = simBlocks[simBlocks.length - 1];
    const prevHash = prevBlock.block_hash;
    const mockHash = pseudoSha256(`${simBlocks.length}:${simUptimeSec}:${eventType}:${prevHash}`);
    simBlocks.push({
        index: simBlocks.length,
        timestamp_ms: simUptimeSec * 1000,
        event_type: eventType,
        description: desc,
        prev_hash: prevHash,
        block_hash: mockHash
    });
}

function resetSimData() {
    simFps = 95.0;
    simChainTampered = false;
    simAlerts = simAlerts.slice(0, 2);
    // restore original 3 blocks
    simBlocks = [
        {
            index: 0,
            timestamp_ms: 15000,
            event_type: 'GENESIS_ANCHOR',
            description: 'Genesis anchor created for ForensiTap firmware v1.0.0',
            prev_hash: '0000000000000000000000000000000000000000000000000000000000000000',
            block_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1'
        },
        {
            index: 1,
            timestamp_ms: 32000,
            event_type: 'NEW_DEVICE_OBSERVED',
            description: 'New device observed: [50:2E:91:0A:02:B0] (STA, RSSI: -42 dBm)',
            prev_hash: '28de3b56d89a1424ce5b083a002498e98b3fca72957b425b0451ff23b2c34aa1',
            block_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00'
        },
        {
            index: 2,
            timestamp_ms: 64000,
            event_type: 'BASELINE_READY',
            description: 'Statistical baseline ready: Mean 92.4 fps, StdDev 8.1 fps',
            prev_hash: '5f91e98b3fca72957b425b0451ff23b2c34aa128de3b56d89a1424ce5b083a00',
            block_hash: '031e9f87a19a9ac7925bb750781fe32b919a778c89b21fae39b7dca46798e1f0'
        }
    ];
    showToast('Simulation baseline reset to normal.');
    renderDemoTick();
}

function pseudoSha256(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
    }
    const hex = Math.abs(hash).toString(16).padStart(8, '0');
    return (hex + hex + hex + hex + hex + hex + hex + hex).substring(0, 64);
}

function exportSimCsv() {
    let csv = 'Index,Timestamp_ms,Event_Type,Description,Prev_Hash,Block_Hash\n';
    for (const b of simBlocks) {
        csv += `${b.index},${b.timestamp_ms},"${b.event_type}","${b.description}",${b.prev_hash},${b.block_hash}\n`;
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `forensitap_evidence_${Date.now()}.csv`;
    a.click();
    showToast('Downloaded evidence log CSV.');
}

// Live UI Renderers
function updateConnectionBadge(online, latencyMs, label) {
    const badge = document.getElementById('connectionBadge');
    if (!badge) return;
    if (online) {
        badge.innerHTML = `<span class="status-dot"></span> ${label || 'ONLINE'} (${latencyMs} ms)`;
        badge.style.background = 'rgba(16, 185, 129, 0.1)';
        badge.style.color = '#10b981';
        badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    } else {
        badge.innerHTML = `<span class="status-dot" style="background:#ef4444"></span> OFFLINE (Click 'Mode: Demo' to test)`;
        badge.style.background = 'rgba(239, 68, 68, 0.1)';
        badge.style.color = '#ef4444';
        badge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    }
}

function updateHealthCard(h) {
    setText('valUptime', `${h.uptime_sec || 0}s`);
    setText('valChannel', `CH ${h.wifi_channel || 11}`);
    setText('valRssi', `${h.rssi_dbm || 0} dBm`);
    setText('valHeap', `${Math.round((h.free_heap_bytes || 0) / 1024)} KB`);
    setText('subIpAddress', h.ip_address || '192.168.1.26');
    setText('subFirmware', h.firmware_version || 'v1.0.0');
}

function updateStats(s) {
    const fps = Math.round(s.current_frame_rate || 0);
    setText('valFps', `${fps} fps`);
    setText('valTotalFrames', (s.total_observed_frames || 0).toLocaleString());
    setText('valDropped', `${s.dropped_frames_count || 0} dropped`);

    // Update real-time chart
    const nowStr = new Date().toLocaleTimeString();
    chartLabels.push(nowStr);
    chartFpsData.push(fps);

    if (chartLabels.length > MAX_CHART_POINTS) {
        chartLabels.shift();
        chartFpsData.shift();
        if (chartBaselineData.length > 0) chartBaselineData.shift();
    }

    if (trafficChart) trafficChart.update('none');
}

function updateFeatures(f) {
    setText('featWindowFps', `${(f.frame_rate || 0).toFixed(1)} fps`);
    setText('featByteRate', `${((f.byte_rate || 0) / 1024).toFixed(1)} KB/s`);
    setText('featAvgSize', `${(f.average_frame_size || 0).toFixed(1)} B`);
    setText('featMgmtRatio', `${((f.management_frame_ratio || 0) * 100).toFixed(1)}%`);
    setText('featBurstScore', (f.traffic_burst_score || 1.0).toFixed(2));

    const b = f.baseline || {};
    const mean = (b.mean_frame_rate || 0).toFixed(1);
    const std = (b.std_frame_rate || 0).toFixed(1);
    const z = (b.frame_rate_zscore || 0).toFixed(2);
    setText('featBaseline', `${mean} ± ${std} fps (Z: ${z > 0 ? '+' : ''}${z})`);

    // Add baseline data to chart
    if (chartBaselineData.length < chartLabels.length) {
        chartBaselineData.push(parseFloat(mean));
    }
}

function updateDevices(d) {
    const devices = d.devices || [];
    setText('valPeers', `${devices.length} / 32`);
    setText('deviceCountBadge', `${devices.length} active`);

    const tbody = document.getElementById('devicesTableBody');
    if (!tbody) return;

    if (devices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#64748b">No devices tracked yet</td></tr>`;
        return;
    }

    // Sort by packet count descending
    devices.sort((a, b) => b.packets - a.packets);

    let html = '';
    for (const dev of devices) {
        const typeBadge = dev.is_ap ? '<span class="badge badge-ap">AP</span>' : '<span class="badge badge-sta">STA</span>';
        const lastSeenSec = Math.round((dev.last_seen_ms || 0) / 1000);
        html += `
            <tr>
                <td><strong>${dev.mac}</strong></td>
                <td>${typeBadge}</td>
                <td>${(dev.packets || 0).toLocaleString()}</td>
                <td><span style="color:${dev.rssi > -65 ? '#10b981' : dev.rssi > -80 ? '#f59e0b' : '#ef4444'}">${dev.rssi} dBm</span></td>
                <td>${lastSeenSec}s</td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

function updateAlerts(a) {
    const alerts = a.alerts || [];
    setText('alertCountBadge', `${alerts.length} stored`);

    const container = document.getElementById('alertsContainer');
    if (!container) return;

    if (alerts.length === 0) {
        container.innerHTML = `<div style="text-align:center;color:#64748b;padding:1.5rem">No anomalies detected (Traffic nominal)</div>`;
        return;
    }

    // Show newest first
    const reversed = [...alerts].reverse();
    let html = '';
    for (const alert of reversed) {
        const sevClass = alert.severity === 'CRITICAL' ? 'alert-critical' :
                         alert.severity === 'HIGH' ? 'alert-high' :
                         alert.severity === 'MEDIUM' ? 'alert-medium' : '';
        const badgeClass = alert.severity === 'CRITICAL' ? 'badge-critical' :
                          alert.severity === 'HIGH' ? 'badge-high' :
                          alert.severity === 'MEDIUM' ? 'badge-medium' :
                          alert.severity === 'LOW' ? 'badge-low' : 'badge-info';

        html += `
            <div class="alert-item ${sevClass}">
                <div class="alert-item-header">
                    <span class="alert-type">${alert.event_type}</span>
                    <span class="badge ${badgeClass}">${alert.severity}</span>
                </div>
                <div class="alert-desc">${alert.description}</div>
                <div class="alert-time">Event #${alert.event_id} • ${(alert.timestamp / 1000).toFixed(1)}s uptime</div>
            </div>
        `;
    }
    container.innerHTML = html;
}

function updateEvidenceChain(logs, verify) {
    const blocks = logs.blocks || [];
    const valid = verify.chain_intact;

    const chainBadge = document.getElementById('chainStatusBadge');
    if (chainBadge) {
        if (valid) {
            chainBadge.innerHTML = `<span class="status-dot"></span> VALID (${blocks.length} BLOCKS)`;
            chainBadge.className = 'status-badge';
            chainBadge.style.color = '#10b981';
        } else {
            chainBadge.innerHTML = `<span class="status-dot" style="background:#ef4444"></span> COMPROMISED`;
            chainBadge.className = 'status-badge';
            chainBadge.style.color = '#ef4444';
        }
    }

    setText('valBlocksMinted', `${verify.total_blocks_created || blocks.length} minted`);
    setText('genesisHashText', logs.genesis_hash ? `${logs.genesis_hash.substring(0, 16)}...` : '---');
    setText('tipHashText', logs.tip_hash ? `${logs.tip_hash.substring(0, 16)}...` : '---');

    const tbody = document.getElementById('evidenceTableBody');
    if (!tbody) return;

    if (blocks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#64748b">No blocks minted</td></tr>`;
        return;
    }

    // Display newest 10 blocks
    const displayBlocks = [...blocks].slice(-10).reverse();
    let html = '';
    for (const b of displayBlocks) {
        const prevSnippet = b.prev_hash.substring(0, 12);
        const blockSnippet = b.block_hash.substring(0, 12);
        html += `
            <tr>
                <td><strong>#${b.index}</strong></td>
                <td>${(b.timestamp_ms / 1000).toFixed(1)}s</td>
                <td><span class="badge badge-info">${b.event_type}</span></td>
                <td>${b.description}</td>
                <td class="hash-cell" title="${b.prev_hash}">${prevSnippet}...</td>
                <td class="hash-cell" title="${b.block_hash}"><strong>${blockSnippet}...</strong></td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

async function triggerChainAudit() {
    showToast('Executing cryptographic hash chain audit...');
    if (operatingMode === 'demo') {
        if (!simChainTampered) {
            showToast(`[+] SHA-256 Audit VERIFIED: ${simBlocks.length} blocks inspected mathematically. Chain tip links directly to Genesis.`);
        } else {
            showToast(`[-] CRITICAL COMPROMISE: Block #1 hash mismatch! Previous hash does not link to Block #2. Chain integrity violation.`);
        }
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/logs/verify`).then(r => r.json());
        if (res.chain_intact) {
            showToast(`[+] Chain Integrity VERIFIED! ${res.blocks_checked} blocks inspected mathematically. No tampering.`);
        } else {
            showToast(`[-] CRITICAL: Chain Compromised at Block #${res.failed_index}: ${res.failure_reason}`);
        }
    } catch (e) {
        showToast(`Audit failed: Could not connect to ${API_BASE_URL}`);
    }
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function showToast(msg) {
    let toast = document.getElementById('dashboardToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'dashboardToast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, 4500);
}
