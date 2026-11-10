#!/usr/bin/env python3
"""
ForensiTap-ESP32: High-Speed Headless Visual Inspection & Viewport Testing Suite
"""

import os
import subprocess
import time
import threading
import http.server

PORT = 8094
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "visual_screenshots")

VIEWPORTS = [
    ("desktop_1920", 1920, 1080),
    ("desktop_1440", 1440, 900),
    ("tablet_1024", 1024, 768),
    ("tablet_768", 768, 1024),
    ("mobile_390", 390, 844)
]

def run_visual_suite():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    server = http.server.HTTPServer(('127.0.0.1', PORT), http.server.SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    print("=" * 70)
    print("      FORENSITAP-ESP32 HIGH-SPEED VISUAL REGRESSION SUITE")
    print("=" * 70)

    results = []
    for name, width, height in VIEWPORTS:
        out_file = os.path.join(OUTPUT_DIR, f"{name}.png")
        url = f"http://127.0.0.1:{PORT}/dashboard/index.html"
        cmd = [
            CHROME_PATH,
            "--headless=new",
            f"--screenshot={out_file}",
            f"--window-size={width},{height}",
            "--hide-scrollbars",
            url
        ]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        elapsed = time.time() - t0
        exists = os.path.exists(out_file)
        size = os.path.getsize(out_file) if exists else 0

        status = "PASSED" if (res.returncode == 0 and exists and size > 10000) else "FAILED"
        results.append((name, width, height, status, size, elapsed))
        print(f"[{status}] {name:<14} ({width}x{height}px) -> {size/1024:.1f} KB in {elapsed:.2f}s")

    server.shutdown()
    print("=" * 70)
    print(f"[*] Visual Suite Completed: {sum(1 for r in results if r[3] == 'PASSED')}/{len(results)} viewports rendered successfully.")
    print("=" * 70)
    return results

if __name__ == '__main__':
    run_visual_suite()
