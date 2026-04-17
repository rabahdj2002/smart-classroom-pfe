# MQTT Real-Time Integration

The website now runs an internal MQTT listener in the Django process (no separate consumer required).

## Runtime behavior

- Listener starts automatically when the Django app starts.
- Listener subscribes to `smartclass/#` by default.
- Listener reconnects automatically if broker/network drops.
- Incoming messages are processed immediately and stored in DB.

## Quick mode toggle (local vs production)

Use environment variable `SMARTCLASS_MODE`:

- `test` (default): MQTT broker host defaults to `127.0.0.1`
- `production`: MQTT broker host defaults to `192.168.70.25` unless you override `DASHBOARD_MQTT_BROKER_HOST`

### Windows (PowerShell)

```powershell
$env:SMARTCLASS_MODE = "test"
```

```powershell
$env:SMARTCLASS_MODE = "production"
```

### Linux

```bash
export SMARTCLASS_MODE=test
```

```bash
export SMARTCLASS_MODE=production
```

You can always override host/port directly with:

- `DASHBOARD_MQTT_BROKER_HOST`
- `DASHBOARD_MQTT_BROKER_PORT`

## Config (in `smartclass/settings.py`)

- `DASHBOARD_MQTT_ENABLED = True`
- `DASHBOARD_MQTT_BROKER_HOST = '192.168.70.25'`
- `DASHBOARD_MQTT_BROKER_PORT = 1883`
- `DASHBOARD_MQTT_TOPIC = 'smartclass/#'`
- `DASHBOARD_MQTT_USERNAME`, `DASHBOARD_MQTT_PASSWORD`
- `DASHBOARD_MQTT_KEEPALIVE_SECONDS = 60`
- `DASHBOARD_MQTT_RECONNECT_DELAY_SECONDS = 3`

## Supported payload format (JSON)

Publish to any topic under `smartclass/#`.

Example:

```json
{
  "classroom_name": "d3",
  "timestamp": "2026-04-16T12:30:05+01:00",
  "teacher_rfid": "TEACHER-ABC123",
  "student_rfids": ["STU-001", "STU-002"],
  "occupied": true,
  "lights_on": true,
  "door": false,
  "projector_on": true,
  "smoke_detected": false,
  "danger_indicator": false
}
```

Accepted keys:

- Classroom identity: `classroom_id` or `classroom_name` or `classroom`
- Teacher RFID: `teacher_rfid` or `staff_rfid`
- Student RFID: `student_rfid` or `student_rfids` or `students`
- Session boundary keys: `new_session`, `session_start`, `start_new_session`, `force_new_session`
- Status keys: `occupied`, `lights_on`, `door`, `projector_on`, `smoke_detected`, `danger_indicator`
- Optional event time: `timestamp` (ISO datetime). If omitted, server time is used.

## DB side effects

- Classroom statuses are updated in real time.
- If a payload marks a new session, any open session for that classroom is closed first.
- Staff RFID attaches the teacher to the active session.
- Student RFID(s) are attached directly to the active session.
- Existing session logic updates occupancy metrics and generates the report on close.

## Notes

- Unknown RFIDs are ignored and logged as warnings.
- If classroom does not exist but `classroom_name` is provided, it is auto-created.
- For Linux production, run Django with a persistent process manager (systemd/supervisor) so the internal listener stays alive.
