# HeisenHelmet Safety Cloud

HeisenHelmet is a high-end IoT safety platform designed for real-time fleet management. It integrates helmet telemetry (GPS, Alcohol, MPU, Battery) with a dynamic web dashboard for supervisor monitoring and automated incident response.

## 🚀 Core Features

- **Real-Time Telemetry**: Live tracking of speed, location, alcohol levels, and helmet status (worn/strapped/tilt).
- **Incident Intelligence**: Automatic crash detection and alcohol threshold alerts with a global notification system.
- **Priority Status Logic**: Intelligent state management (Accident > Drunk > Online/Offline).
- **Fleet Management**: Centralized settings for speed limits, safety thresholds, and map refresh rates.
- **Production Ready**: Full support for remote hosting, Cloudflare subdomains, and WSS (Secure WebSockets).
- **Documentation In-App**: Built-in protocol guides and administrator manuals.

## 🛠️ Tech Stack

- **Backend**: Django 6.0.3 (Python 3.10+)
- **Messaging**: MQTT (Paho MQTT) with WebSocket Secure (WSS) support.
- **Database**: SQLite (Production-ready state management).
- **Frontend**: Glassmorphism UI with Oklahoma LCH (oklch) color system.

## 📂 Project Structure

- `backend/dashboard/`: Core logic, MQTT listener, and safety models.
- `backend/smarthelmet/`: Project configuration and security settings.
- `backend/static/`: Custom CSS and dashboard assets.
- `DASHBOARD_TECHNICAL_GUIDE.md`: Deep dive into system architecture and IoT data flow.
- `DASHBOARD_USER_GUIDE.md`: Administrator manual and safety protocol reference.

## 🏁 Quick Start

### 1. Setup Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 2. Initialize Database
```powershell
cd backend
python manage.py migrate
```

### 3. Launch Platform
```powershell
python manage.py runserver 0.0.0.0:8000
```
*Note: The MQTT background listener starts automatically with the server.*

## 🌐 Remote Hosting (Cloudflare)
To host on a subdomain (e.g., `helmet.yourdomain.com`):
1. Configure `CSRF_TRUSTED_ORIGINS` in `settings.py`.
2. Set your **Public WebSocket Host** in the platform's Settings page.
3. Ensure your MQTT broker handles WSS (Port 443 recommended for Cloudflare).

## 🛡️ License
Proprietary HeisenHelmet Safety Protocol.
