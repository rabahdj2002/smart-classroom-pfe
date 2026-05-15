"""Standalone MQTT runner (optional).

The website now runs MQTT internally via dashboard.apps.DashboardConfig.ready().
This script remains as a manual fallback for diagnostics.
"""

import os
import sys

import django

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')
django.setup()

from dashboard.mqtt_listener import _mqtt_loop  # noqa: E402


if __name__ == '__main__':
    _mqtt_loop()
