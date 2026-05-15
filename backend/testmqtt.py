import argparse
import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


def build_dummy_payload(classroom_name):
    teacher_rfids = ["123456789123", "TEACHER-XYZ789"]
    student_rfids_pool = [
        "1234567891254",
        "156",
        "STU-003",
        "STU-004",
        "STU-005",
        "STU-006",
    ]

    student_count = random.randint(1, 4)
    selected_students = random.sample(student_rfids_pool, student_count)

    payload = {
        "classroom_name": classroom_name,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "teacher_rfid": random.choice(teacher_rfids),
        "student_rfids": selected_students,
        "occupied": True,
        "lights_on": random.choice([True, False]),
        "door": random.choice([True, False]),
        "projector_on": random.choice([True, False]),
        "smoke_detected": random.choice([False, False, False, True]),
        "danger_indicator": random.choice([False, False, True]),
    }
    return payload


def main():
    env_mode = os.getenv("SMARTCLASS_MODE", "test").strip().lower()

    parser = argparse.ArgumentParser(description="Publish dummy SmartClass MQTT data")
    parser.add_argument("--mode", choices=["test", "production"], default=env_mode, help="Runtime mode for default host selection")
    parser.add_argument("--host", default=None, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic", default="", help="MQTT topic (default: smartclass/classrooms/<classroom>/events)")
    parser.add_argument("--classroom", default="d3", help="Classroom name in payload")
    parser.add_argument("--count", type=int, default=5, help="Number of messages to publish")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between messages")
    args = parser.parse_args()

    if not args.host:
        args.host = "127.0.0.1" if args.mode == "test" else "192.168.70.25"

    if not args.topic:
        args.topic = f"smartclass/classrooms/{args.classroom}/events"

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    try:
        client.connect(args.host, args.port, 60)
    except OSError as exc:
        print(f"Failed to connect to MQTT broker {args.host}:{args.port} ({exc})")
        return

    client.loop_start()

    print(f"Connected to MQTT broker {args.host}:{args.port}")
    print(f"Mode: {args.mode}")
    print(f"Publishing to topic: {args.topic}")
    print(f"Payload classroom_name: {args.classroom}")

    try:
        for i in range(args.count):
            payload = build_dummy_payload(args.classroom)
            payload_json = json.dumps(payload)
            result = client.publish(args.topic, payload_json, qos=0, retain=False)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[{i + 1}/{args.count}] Sent: {payload_json}")
            else:
                print(f"[{i + 1}/{args.count}] Failed to send, rc={result.rc}")

            if i < args.count - 1:
                time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
