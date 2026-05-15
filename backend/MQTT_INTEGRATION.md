# MQTT Integration Guide

This project uses one MQTT flow for devices and one for the dashboard.

The server listens on `smartclass/#` and uses its own timestamp for every stored event.

## 1. Topics

### Device to dashboard

- `smartclass/classrooms/<classroom_name>/events`
- `smartclass/classrooms/<classroom_name>/access/request`
- `smartclass/classrooms/<classroom_name>/attendance/request`
- `smartclass/classrooms/<classroom_name>/door-delay/request`

### Dashboard to device

- `smartclass/classrooms/<classroom_name>/commands`
- `smartclass/classrooms/<classroom_name>/access/response`
- `smartclass/classrooms/<classroom_name>/door-delay/response`

## 2. Device to dashboard payloads

### A. Classroom state / live events

Use this when the room state changes.

```json
{
  "classroom_name": "d3",
  "occupied": true,
  "lights_on": true,
  "door": false,
  "projector_on": true,
  "smoke_detected": false,
  "danger_indicator": false,
  "teacher_rfid": "123456789123",
  "new_session": false
}
```

Supported keys:

- `classroom_id`, `classroom_name`, `classroom`
- `teacher_rfid`, `staff_rfid`
- `student_rfid`, `student_rfids`, `students`
- `occupied`, `lights_on`, `door`, `projector_on`, `smoke_detected`, `danger_indicator`
- `new_session`, `session_start`, `start_new_session`, `force_new_session`

### B. Teacher access request

Send this before a teacher session or an inspection.

```json
{
  "teacher_rfid": "123456789123",
  "request_id": "door-req-001"
}
```

Required field:

- `teacher_rfid`, `staff_rfid`, or `rfid_number`

### C. Student attendance request

Send this after the teacher session is open.

```json
{
  "student_rfids": ["1234567891254", "STU-002"],
  "event": "attendance_request"
}
```

Supported keys:

- `student_rfid` for one student
- `student_rfids` or `students` for multiple students
- `event`, `command`, `request`, or `type` as optional markers

### D. Door delay request

Ask the server for the configured close delay.

```json
{
  "command": "door_delay_request",
  "request_id": "delay-001"
}
```

The response is the delay in minutes as a plain number.

## 3. Dashboard to device payloads

### A. Classroom commands

The dashboard publishes control commands to:

```text
smartclass/classrooms/<classroom_name>/commands
```

Payload format:

```json
{
  "command": "lights",
  "classroom_id": 3,
  "classroom_name": "d3",
  "value": true
}
```

Supported commands:

- `lights`
- `projector`
- `smoke_reset`

### B. Teacher access response

Response topic:

```text
smartclass/classrooms/<classroom_name>/access/response
```

Example response:

```json
{
  "event": "teacher_access_response",
  "request_id": "door-req-001",
  "approved": true,
  "reason": "authorized_in_time_window",
  "classroom_id": 3,
  "classroom_name": "d3",
  "teacher_id": 12,
  "teacher_name": "Prof. Ali",
  "access_window_minutes": 10,
  "slot_index": 0,
  "slot_label": "08:00 - 09:30",
  "slot_start": "2026-04-20T08:00:00+01:00",
  "slot_end": "2026-04-20T09:30:00+01:00",
  "checked_at": "2026-04-20T08:04:00+01:00"
}
```

Important reasons:

- `authorized_in_time_window` = class session opened
- `authorized_immediate_override` = class session opened by manual override
- `authorized_admin_override` = inspection created immediately

### C. Door delay response

Response topic:

```text
smartclass/classrooms/<classroom_name>/door-delay/response
```

Response example:

```text
10
```

## 4. Session behavior

- Class sessions are created for teachers.
- Inspection sessions are created for administrators only.
- Inspection sessions are closed immediately and do not use students, duration, or reports.
- Attendance requests add students to the active class session.
- If there is no open class session, the attendance request is ignored.
- The server always uses its own time when storing events.

## 5. Typical flow

1. Device sends `access/request` with a teacher RFID.
2. Server validates the teacher.
3. If the teacher is a professor, a class session opens.
4. If the teacher is an administrator, an inspection record is created.
5. Device sends `attendance/request` with student RFIDs.
6. Server attaches the students to the open class session.

## 6. Quick CLI tests

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -t smartclass/classrooms/d3/access/request -m "{\"teacher_rfid\":\"123456789123\"}"
mosquitto_pub -h 127.0.0.1 -p 1883 -t smartclass/classrooms/d3/attendance/request -m "{\"student_rfids\":[\"STU-001\",\"STU-002\"]}"
mosquitto_pub -h 127.0.0.1 -p 1883 -t smartclass/classrooms/d3/door-delay/request -m "{\"command\":\"door_delay_request\"}"
mosquitto_sub -h 127.0.0.1 -p 1883 -t smartclass/classrooms/d3/commands -v
```