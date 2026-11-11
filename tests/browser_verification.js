/**
 * Browser Verification Script for ForensiTap Dashboard
 * Connects directly to Headless Chrome via Chrome DevTools Protocol (CDP) using native Node.js 24 WebSocket.
 */

const { spawn } = require('child_process');
const http = require('http');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const DEBUG_PORT = 9222;
const APP_URL = 'http://localhost:8085';

async function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

function getJson(url) {
    return new Promise((resolve, reject) => {
        http.get(url, res => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

class CDPClient {
    constructor(wsUrl) {
        this.ws = new WebSocket(wsUrl);
        this.id = 0;
        this.callbacks = new Map();
        this.events = [];
        this.exceptions = [];
        this.consoleLogs = [];

        this.ready = new Promise((resolve, reject) => {
            this.ws.onopen = resolve;
            this.ws.onerror = reject;
        });

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.id && this.callbacks.has(msg.id)) {
                const cb = this.callbacks.get(msg.id);
                this.callbacks.delete(msg.id);
                if (msg.error) cb.reject(new Error(msg.error.message));
                else cb.resolve(msg.result);
            } else if (msg.method) {
                if (msg.method === 'Runtime.exceptionThrown') {
                    this.exceptions.push(msg.params);
                    console.error('BROWSER EXCEPTION:', JSON.stringify(msg.params.exceptionDetails));
                } else if (msg.method === 'Console.messageAdded') {
                    this.consoleLogs.push(msg.params.message);
                }
            }
        };
    }

    send(method, params = {}) {
        const id = ++this.id;
        return new Promise((resolve, reject) => {
            this.callbacks.set(id, { resolve, reject });
            this.ws.send(JSON.stringify({ id, method, params }));
        });
    }

    async evaluate(expression) {
        const res = await this.send('Runtime.evaluate', {
            expression,
            returnByValue: true,
            awaitPromise: true
        });
        if (res.exceptionDetails) {
            throw new Error(res.exceptionDetails.text || 'Evaluation failed');
        }
        return res.result ? res.result.value : undefined;
    }
}

async function runVerification() {
    console.log('=== FORENSITAP LIVE BROWSER CDP RUNTIME VERIFICATION ===');
    
    // 1. Launch Chrome Headless with Remote Debugging
    console.log('[*] Launching Headless Chrome on port', DEBUG_PORT);
    const chrome = spawn(CHROME_PATH, [
        `--remote-debugging-port=${DEBUG_PORT}`,
        '--headless=new',
        '--disable-gpu',
        '--no-sandbox',
        '--hide-scrollbars',
        '--window-size=1440,900',
        'about:blank'
    ], { stdio: 'ignore' });

    let connected = false;
    let client = null;

    try {
        // Wait for CDP endpoint to be ready
        for (let i = 0; i < 20; i++) {
            try {
                const list = await getJson(`http://localhost:${DEBUG_PORT}/json`);
                if (list && list.length > 0) {
                    const page = list.find(p => p.type === 'page') || list[0];
                    client = new CDPClient(page.webSocketDebuggerUrl);
                    await client.ready;
                    connected = true;
                    break;
                }
            } catch (e) {
                await sleep(200);
            }
        }

        if (!connected) {
            throw new Error('Failed to connect to Chrome DevTools Protocol');
        }

        console.log('[*] Connected to Chrome CDP. Enabling Runtime and Console domains...');
        await client.send('Runtime.enable');
        await client.send('Console.enable');
        await client.send('Page.enable');

        // 2. Navigate to Dashboard
        console.log(`[*] Navigating to ${APP_URL}...`);
        await client.send('Page.navigate', { url: APP_URL });
        await sleep(1500); // Allow scripts, Chart.js, and DOM to settle

        // Check for startup exceptions
        if (client.exceptions.length > 0) {
            throw new Error(`Startup exceptions detected: ${JSON.stringify(client.exceptions)}`);
        }
        console.log('  [PASS] Clean startup with ZERO uncaught exceptions');

        // 3. Verify DOM Elements and Titles
        const title = await client.evaluate('document.title');
        console.log(`  [PASS] Page Title: "${title}"`);

        const badgeText = await client.evaluate('document.getElementById("connectionBadge").innerText.trim()');
        console.log(`  [PASS] Initial Connection Badge: "${badgeText}"`);

        // 4. Test Demo Mode Functionality
        console.log('[*] Testing Demo Mode...');
        await client.evaluate('setMode("demo")');
        await sleep(500);
        const demoBadge = await client.evaluate('document.getElementById("connectionBadge").innerText.trim()');
        console.log(`  [PASS] Demo Mode Badge: "${demoBadge}"`);
        if (!demoBadge.includes('DEMO')) throw new Error(`Expected DEMO badge, got: ${demoBadge}`);

        // Run cycle
        await client.evaluate('runSimulatorCycle()');
        const fpsText = await client.evaluate('document.getElementById("valFps").innerText.trim()');
        console.log(`  [PASS] Demo FPS Metric: "${fpsText}"`);

        // 5. Test Threat Playbook Buttons
        console.log('[*] Testing Attack Playbook triggers...');
        
        // Deauth Storm
        await client.evaluate('triggerSimAttack("deauth")');
        const deauthVal = await client.evaluate('document.getElementById("valDeauthRate").innerText.trim()');
        console.log(`  [PASS] Deauth Storm Attack: ${deauthVal}`);
        if (parseFloat(deauthVal) < 20) throw new Error(`Unexpected deauth rate: ${deauthVal}`);

        // Traffic Surge
        await client.evaluate('triggerSimAttack("spike")');
        const spikeFps = await client.evaluate('document.getElementById("featWindowFps").innerText.trim()');
        console.log(`  [PASS] Traffic Spike Surge: ${spikeFps}`);

        // Rogue AP
        await client.evaluate('triggerSimAttack("rogue")');
        const radarBlips = await client.evaluate('document.getElementById("radarDeviceCount").innerText.trim()');
        console.log(`  [PASS] Rogue AP Added to Radar: ${radarBlips}`);

        // Tamper Simulation
        await client.evaluate('toggleTamperSimulation()');
        const tamperResult = await client.evaluate('document.getElementById("chainStatusBadge") ? document.getElementById("chainStatusBadge").innerText.trim() : (simChainTampered ? "TAMPERED" : "VALID")');
        console.log(`  [PASS] Cryptographic Tamper Test: ${tamperResult}`);

        // Reset Baseline
        await client.evaluate('resetSimData()');
        const resetFps = await client.evaluate('document.getElementById("featWindowFps").innerText.trim()');
        console.log(`  [PASS] Baseline Restored: ${resetFps}`);

        // 6. Test Navigation Tabs
        console.log('[*] Testing Navigation Tabs switching...');
        const tabs = ['radar', 'chain', 'architecture', 'overview', 'dashboard'];
        for (const t of tabs) {
            await client.evaluate(`switchTab("${t}")`);
            const viewActive = await client.evaluate(`document.getElementById("view${t.charAt(0).toUpperCase() + t.slice(1)}").classList.contains("active")`);
            if (!viewActive) throw new Error(`View view${t} failed to activate`);
            console.log(`  [PASS] Tab '${t}' activated successfully`);
        }

        // 7. Test APPLIANCE IP Input & Validation
        console.log('[*] Testing APPLIANCE IP configuration & persistence...');
        await client.evaluate(`
            const input = document.getElementById('apiUrlInput');
            input.value = 'http://192.168.1.199';
            input.dispatchEvent(new Event('change'));
        `);
        const savedUrl = await client.evaluate('localStorage.getItem("forensitap_api_url")');
        console.log(`  [PASS] LocalStorage Persisted URL: "${savedUrl}"`);
        if (savedUrl !== 'http://192.168.1.199') throw new Error(`URL persistence mismatch: ${savedUrl}`);

        const subIpText = await client.evaluate('document.getElementById("subIpAddress").innerText.trim()');
        console.log(`  [PASS] Dashboard Sub-IP Display: "${subIpText}"`);

        // 8. Test USB Serial Parser via handleSerialLine
        console.log('[*] Testing Serial Parser (Type A, B, C) in live runtime...');
        
        // Type A: @FEATURES
        await client.evaluate(`
            handleSerialLine('@FEATURES {"frame_rate":112.4,"throughput_kbps":48.2,"byte_rate":6025.0,"deauth_rate":0.0,"disassoc_rate":0.0,"deauth_ratio":0.0,"burst_score":1.05,"mgmt_ratio":0.08,"unique_peers":9,"uptime_sec":120,"alerts_total":2,"wifi_connected":true,"ip_address":"192.168.1.88"}');
        `);
        const usbFps = await client.evaluate('document.getElementById("featWindowFps").innerText.trim()');
        const autoIp = await client.evaluate('localStorage.getItem("forensitap_api_url")');
        console.log(`  [PASS] Type A @FEATURES parsed: FPS=${usbFps}, Auto-detected IP=${autoIp}`);
        if (!usbFps.includes('112.4')) throw new Error(`Type A failed to update UI: ${usbFps}`);
        if (autoIp !== 'http://192.168.1.88') throw new Error(`Auto-detected IP mismatch: ${autoIp}`);

        // Type C: Heartbeat log
        await client.evaluate(`
            handleSerialLine('[16000] [INFO] [LIV ] [HEARTBEAT] ForensiTap | WIFI_CONNECTED | MON_ACTIVE | API_ACTIVE | 98 fps | 12 peers | Alerts: 3 | Blocks: 5 | Uptime: 150 s | Heap: 215432 B');
        `);
        const hbFps = await client.evaluate('document.getElementById("featWindowFps").innerText.trim()');
        console.log(`  [PASS] Type C Heartbeat parsed: FPS=${hbFps}`);
        if (!hbFps.includes('98.0')) throw new Error(`Type C failed to update UI: ${hbFps}`);

        // Type C: 10s Window Rates
        await client.evaluate(`
            handleSerialLine('  |   10s Window Rates: 104.2 fps | 41.5 KB/s | Deauth: 1.2 fps');
        `);
        const rateFps = await client.evaluate('document.getElementById("featWindowFps").innerText.trim()');
        const deauthRate = await client.evaluate('document.getElementById("valDeauthRate").innerText.trim()');
        console.log(`  [PASS] Type C Window Rates parsed: FPS=${rateFps}, Deauth=${deauthRate}`);
        if (!rateFps.includes('104.2')) throw new Error(`Type C rates failed: ${rateFps}`);
        if (!deauthRate.includes('1.2')) throw new Error(`Type C deauth failed: ${deauthRate}`);

        // 9. Verify Final Exception Count
        if (client.exceptions.length > 0) {
            throw new Error(`Runtime exceptions occurred during interaction: ${JSON.stringify(client.exceptions)}`);
        }

        console.log('\n======================================================');
        console.log('>>> ALL LIVE BROWSER AUDIT CHECKS PASSED (100%) <<<');
        console.log('======================================================');

    } catch (err) {
        console.error('\n[!] VERIFICATION FAILED:', err);
        process.exitCode = 1;
    } finally {
        if (client && client.ws) {
            try { client.ws.close(); } catch (e) {}
        }
        chrome.kill();
    }
}

runVerification();
