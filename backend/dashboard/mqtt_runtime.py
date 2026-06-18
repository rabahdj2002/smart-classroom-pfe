from django.conf import settings

from .models import SystemSettings


def _to_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def should_use_tls(broker_host, broker_port, fallback_enabled=False):
    host = str(broker_host or "").strip().lower()
    port = _to_int(broker_port, 1883)

    if port in {8883, 8884}:
        return True

    if host in {"127.0.0.1", "localhost", "::1"} and port == 1883:
        return False

    if "hivemq.cloud" in host:
        return True

    return _to_bool(fallback_enabled, default=False)


def get_mqtt_runtime_config():
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

    broker_host = (settings_obj.mqtt_broker_host or getattr(settings, "DASHBOARD_MQTT_BROKER_HOST", "127.0.0.1")).strip()
    broker_port = _to_int(settings_obj.mqtt_broker_port, _to_int(getattr(settings, "DASHBOARD_MQTT_BROKER_PORT", 1883), 1883))
    username = settings_obj.mqtt_username or getattr(settings, "DASHBOARD_MQTT_USERNAME", "")
    password = settings_obj.mqtt_password or getattr(settings, "DASHBOARD_MQTT_PASSWORD", "")
    topic_wildcard = settings_obj.mqtt_topic_wildcard or getattr(settings, "DASHBOARD_MQTT_TOPIC", "smartclass/#")
    keepalive = _to_int(getattr(settings, "DASHBOARD_MQTT_KEEPALIVE_SECONDS", 60), 60)
    reconnect_delay = _to_int(getattr(settings, "DASHBOARD_MQTT_RECONNECT_DELAY_SECONDS", 3), 3)
    fallback_tls = getattr(settings, "DASHBOARD_MQTT_TLS_ENABLED", False)

    tls_enabled = should_use_tls(broker_host, broker_port, fallback_enabled=fallback_tls)

    return {
        "broker_host": broker_host,
        "broker_port": broker_port,
        "username": username,
        "password": password,
        "topic_wildcard": topic_wildcard,
        "keepalive": keepalive,
        "reconnect_delay": reconnect_delay,
        "tls_enabled": tls_enabled,
    }


def configure_mqtt_client(client, runtime_config):
    if runtime_config.get("tls_enabled"):
        client.tls_set()

    username = runtime_config.get("username")
    if username:
        client.username_pw_set(username=username, password=runtime_config.get("password") or None)