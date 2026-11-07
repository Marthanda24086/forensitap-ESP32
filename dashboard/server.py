#!/usr/bin/env python3
"""
ForensiTap-ESP32: Local Web Dashboard Server
Stage 13 Implementation

Hosts the ForensiTap web dashboard locally and opens the browser.
Usage:
    python dashboard/server.py [--port 8080] [--esp-ip 192.168.1.26]
"""

import argparse
import http.server
import os
import socketserver
import webbrowser

DEFAULT_PORT = 8080

def main():
    parser = argparse.ArgumentParser(description="ForensiTap Dashboard Local Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local HTTP port (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    dashboard_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(dashboard_dir)

    handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}"
        print("=" * 70)
        print("     FORENSITAP-ESP32 LIVE WEB DASHBOARD SERVER")
        print("=" * 70)
        print(f"[*] Dashboard URL    : {url}")
        print(f"[*] Serving Directory: {dashboard_dir}")
        print(f"[*] Connected ESP32  : http://192.168.1.26")
        print("=" * 70)
        print("[*] Press Ctrl+C to terminate local server.")

        if not args.no_browser:
            webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] Server shutdown cleanly.")

if __name__ == '__main__':
    main()
