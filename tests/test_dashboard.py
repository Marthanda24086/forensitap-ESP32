#!/usr/bin/env python3
"""
ForensiTap-ESP32: Web Dashboard Integrity Tests
Stage 13 Implementation

Validates dashboard structure, DOM elements, CSS styles, and ensures
JavaScript endpoint bindings accurately match the firmware REST API.
"""

import os
import re
import unittest

class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard')
        self.html_path = os.path.join(self.dashboard_dir, 'index.html')
        self.css_path = os.path.join(self.dashboard_dir, 'style.css')
        self.js_path = os.path.join(self.dashboard_dir, 'app.js')

    def test_files_exist(self):
        self.assertTrue(os.path.exists(self.html_path), "index.html missing")
        self.assertTrue(os.path.exists(self.css_path), "style.css missing")
        self.assertTrue(os.path.exists(self.js_path), "app.js missing")

    def test_html_dom_elements(self):
        with open(self.html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        required_ids = [
            'apiUrlInput',
            'intervalSelect',
            'togglePollingBtn',
            'connectionBadge',
            'valUptime',
            'valFps',
            'valChannel',
            'valPeers',
            'valBlocksMinted',
            'trafficChartCanvas',
            'devicesTableBody',
            'evidenceTableBody',
            'alertsContainer',
            'auditChainBtn',
            'exportCsvBtn',
            'featWindowFps',
            'featByteRate',
            'featAvgSize',
            'featMgmtRatio',
            'featBurstScore',
            'featBaseline'
        ]

        for elem_id in required_ids:
            self.assertIn(f'id="{elem_id}"', html, f"Missing DOM element id: {elem_id}")

    def test_javascript_api_routes(self):
        with open(self.js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        required_endpoints = [
            '/api/health',
            '/api/stats',
            '/api/features',
            '/api/devices',
            '/api/alerts',
            '/api/logs',
            '/api/logs/verify',
            '/api/export'
        ]

        for ep in required_endpoints:
            self.assertIn(ep, js, f"JavaScript does not bind to API endpoint: {ep}")

    def test_css_rules(self):
        with open(self.css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('--bg-dark:', css)
        self.assertIn('--cyan-primary:', css)
        self.assertIn('.kpi-card', css)
        self.assertIn('.chart-container', css)
        self.assertIn('.status-badge', css)

if __name__ == '__main__':
    unittest.main()
