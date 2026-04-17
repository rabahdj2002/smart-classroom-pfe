# Smart Classroom Platform

Smart Classroom Platform is a Django-based control center for classroom operations.
It combines live MQTT events from classroom devices with a web dashboard used by staff
to monitor rooms, manage sessions, and generate attendance reports.

## Core Features

- Real-time classroom status via MQTT (occupancy, lights, projector, door, smoke, danger)
- Session lifecycle management (start, split, close, auto-finish)
- Attendance capture from RFID payloads (teacher + students)
- PDF attendance reports with session summary and student roster
- Optional report email delivery through SMTP
- Admin controls for pagination, UI density, KPI badges, and bulk actions
- MQTT integration guide in-app for device developers

## Tech Stack

- Python 3.10+
- Django 5.1
- SQLite (default)
- MQTT (paho-mqtt)
- ReportLab (PDF generation)

## Repository Layout

- backend/ - Django project
- backend/dashboard/ - main application (views, models, MQTT, reporting)
- backend/smartclass/ - Django project settings and URLs
- backend/static/ - dashboard static assets
- template/ - original UI template assets (reference)

## Quick Start

### 1) Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r backend/requirements.txt
```

### 3) Apply migrations

```powershell
python backend/manage.py migrate
```

### 4) Create admin user (if needed)

```powershell
python backend/manage.py createsuperuser
```

### 5) Run development server

```powershell
python backend/manage.py runserver
```

Open: http://127.0.0.1:8000

## Settings You Can Control In The UI

Open Settings page in the dashboard to configure:

- Auto-finish timing and interval
- Pagination defaults and sessions order
- Bulk actions, KPI badges, compact mode
- SMTP report email delivery
- MQTT broker host/port/topic wildcard
- MQTT production/test mode toggle

## MQTT Integration

### Device sends events to platform

Topic pattern:

```text
smartclass/classrooms/<classroom_name>/events
```

Typical payload:

```json
{
	"classroom_name": "d3",
	"timestamp": "2026-04-17T15:10:05+01:00",
	"teacher_rfid": "123456789123",
	"student_rfids": ["1234567891254", "STU-002"],
	"occupied": true,
	"lights_on": true,
	"door": false,
	"projector_on": true,
	"smoke_detected": false,
	"danger_indicator": false,
	"new_session": false
}
```

### Device receives commands from platform

Subscribe to:

```text
smartclass/classrooms/<classroom_name>/commands
```

Command payload shape:

```json
{
	"command": "lights",
	"classroom_id": 3,
	"classroom_name": "d3",
	"value": true
}
```

Supported commands:

- lights
- projector
- smoke_reset

## Useful Management Commands

```powershell
python backend/manage.py check
python backend/manage.py makemigrations
python backend/manage.py migrate
```

## Test Publisher

Use the built-in MQTT test script:

```powershell
python backend/testmqtt.py --host <broker_host> --port <broker_port> --classroom d3 --count 3 --interval 1
```

## Production Notes

- Set DEBUG=False before deployment
- Restrict ALLOWED_HOSTS to known hostnames/IPs
- Use a secure secret key from environment
- Configure SMTP only if report email is enabled
- Keep MQTT broker credentials private

## Troubleshooting

- No dashboard updates: verify broker host/port and topic wildcard
- Unknown RFID warnings: ensure RFID values exist in Staff/Student records
- Commands not received: verify device is subscribed to the room command topic
- Report emails failing: verify SMTP host, port, credentials, and from email

## License

Internal academic project.
