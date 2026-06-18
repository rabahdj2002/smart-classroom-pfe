# Smart Classroom Node - MQTT API Reference

This document outlines every MQTT topic published by the node to the server, and the exact commands/topics the node accepts from the server.

> [!NOTE]
> `<name>` in the topics below corresponds to the dynamically/statically configured classroom name (e.g., `d3`).

---

## 📤 1. Published by Node (Outgoing to Server)

### 1.1 Access Requests
When a teacher scans a card that is not in the local offline whitelist, the node asks the server to authorize it.
- **Topic:** `smartclass/classrooms/<name>/access/request`
- **Format:**
  ```json
  {
    "event": "access_request",
    "classroom_name": "<name>",
    "data": {
      "teacher_rfid": "3C00C653C6",
      "request_id": "A1B2C3D4"
    }
  }
  ```

### 1.2 Attendance Requests
When a student scans their card while the room is unlocked (an active session).
- **Topic:** `smartclass/classrooms/<name>/attendance/request`
- **Format:**
  ```json
  {
    "event": "attendance_request",
    "classroom_name": "<name>",
    "data": {
      "student_rfids": ["AABBCCDD"]
    }
  }
  ```

### 1.3 State Machine Events
Emitted when access is approved, denied, timed out, or a local admin bypasses the lock.
- **Topic:** `smartclass/classrooms/<name>/events`
- **Format (Access Result):**
  ```json
  {
    "event": "access_result",
    "classroom_name": "<name>",
    "data": {
      "status": "success" | "rejected" | "timeout",
      "reason": "" | "denied_by_server" | "server_no_response"
    }
  }
  ```
- **Format (Admin Bypass):**
  ```json
  {
    "event": "admin_access",
    "classroom_name": "<name>",
    "data": {
      "status": "success",
      "reason": "local_whitelist"
    }
  }
  ```

### 1.4 Dashboard Telemetry (Room State)
Periodic snapshots (or forced updates) representing the physical state of the room.
- **Topic:** `smartclass/classrooms/<name>/events`
- **Retained:** `true`
- **Format:**
  ```json
  {
    "event": "room_state",
    "classroom_name": "<name>",
    "data": {
      "occupied": true,
      "occupancy_detected": true,
      "pir_last_activity": 1234567,
      "door_unlocked": true,
      "teacher_rfid": "3C00C653C6" 
    }
  }
  ```

### 1.5 Node Heartbeat (Health)
Periodic ping to show the ESP32 is online.
- **Topic:** `smartclass/classrooms/<name>/health`
- **Retained:** `true`
- **Format:**
  ```json
  {
    "event": "heartbeat",
    "classroom_name": "<name>",
    "data": {
      "status": "alive",
      "uptime": 3600,
      "occupied": false,
      "occupancy_detected": false,
      "last_activity_ms": 1234567
    }
  }
  ```

### 1.6 RFID Reader Diagnostics
Periodic telemetry regarding the RS485 communication stability of the card readers.
- **Topic:** `smartclass/classrooms/<name>/reader_status`
- **Retained:** `true`
- **Format:**
  ```json
  {
    "classroom_name": "<name>",
    "timestamp": 123456789,
    "readers": {
      "outside": {
        "responsive": true,
        "alive": true,
        "frames_received": 1500,
        "checksum_errors": 2,
        "timeouts": 0,
        "last_byte_ms": 123456
      },
      "inside": { ... }
    }
  }
  ```

---

## 📥 2. Accepted by Node (Incoming from Server)

### 2.1 Access Response
The server's mandatory reply to an `access_request`. The `request_id` must match perfectly.
- **Topic:** `smartclass/classrooms/<name>/access/response`
- **Format:**
  ```json
  {
    "event": "access_response",
    "request_id": "A1B2C3D4",
    "approved": true
  }
  ```

### 2.2 Device Commands
No MQTT hardware control commands are supported by this API.
- Commands related to lighting and projector control are intentionally excluded.
- Only the response/configuration topics documented below are accepted from the server.

### 2.3 Local Whitelist Configuration
Update the offline RFID whitelist dynamically without recompiling.
- **Topic:** `/config/update` *(Global topic, affects all listening nodes)*
- **Retained:** `false` (CRITICAL)
- **Format:**
  ```json
  {
    "command": "add_admin" | "remove_admin" | "add_maintenance" | "remove_maintenance",
    "uid": "3C00C653C6"
  }
  ```

### 2.4 Network & Broker Hot-Swap
Instructs the node to connect to a new WiFi network and/or MQTT Broker dynamically.
- **Topic:** `/config/network` *(Global topic)*
- **Retained:** `false` (CRITICAL)
- **Format:**
  ```json
  {
    "ssid": "New_WiFi",
    "pass": "Password123",
    "broker": "192.168.1.100",
    "port": 1883
  }
  ```
