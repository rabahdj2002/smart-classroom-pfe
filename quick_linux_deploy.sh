#!/usr/bin/env bash
set -euo pipefail

# Quick Linux deploy for SmartClass.
# What it does:
# 1) Pulls latest code from GitHub
# 2) Installs/updates OS and Python dependencies
# 3) Applies migrations and collects static files
# 4) Creates/updates systemd service files
# 5) Runs daemon-reload and restarts services

APP_NAME="${APP_NAME:-smartclass}"
BRANCH="${BRANCH:-main}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
BACKEND_DIR="${BACKEND_DIR:-${PROJECT_ROOT}/backend}"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BIND_ADDR="${BIND_ADDR:-0.0.0.0}"
BIND_PORT="${BIND_PORT:-8001}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}.service}"
ENV_DIR="${ENV_DIR:-/etc/${APP_NAME}}"
ENV_FILE="${ENV_FILE:-${ENV_DIR}/${APP_NAME}.env}"
DAEMON_SERVICE="${DAEMON_SERVICE:-mosquitto.service}"

if [[ "${EUID}" -eq 0 ]]; then
  RUN_USER="${RUN_USER:-${SUDO_USER:-root}}"
else
  RUN_USER="${RUN_USER:-${USER}}"
fi
RUN_GROUP="${RUN_GROUP:-$(id -gn "${RUN_USER}")}" 

log() {
  printf '[deploy] %s\n' "$*"
}

require_path() {
  local target="$1"
  local label="$2"
  if [[ ! -e "${target}" ]]; then
    echo "ERROR: ${label} not found: ${target}" >&2
    exit 1
  fi
}

run_as_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    sudo -u "${RUN_USER}" "$@"
  else
    "$@"
  fi
}

run_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_path "${PROJECT_ROOT}/.git" "Git repository"
require_path "${BACKEND_DIR}/manage.py" "Django manage.py"
require_path "${BACKEND_DIR}/requirements.txt" "Python requirements"

log "1/8 Pulling latest GitHub code from branch ${BRANCH}"
git -C "${PROJECT_ROOT}" fetch origin "${BRANCH}"
if ! git -C "${PROJECT_ROOT}" pull --ff-only origin "${BRANCH}"; then
  echo "ERROR: git pull --ff-only failed. Commit/stash local changes and retry." >&2
  exit 1
fi

log "2/8 Installing OS dependencies (APT if available)"
if command -v apt-get >/dev/null 2>&1; then
  run_sudo apt-get update
  run_sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    libpq-dev \
    pkg-config
else
  log "apt-get not found. Skipping OS package installation."
fi

log "3/8 Creating/updating virtual environment"
if [[ ! -d "${VENV_DIR}" ]]; then
  run_as_user "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi
run_as_user "${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel
run_as_user "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

log "4/8 Running Django migrations"
run_as_user env \
  DJANGO_SETTINGS_MODULE=smartclass.settings \
  SMARTCLASS_MODE=production \
  "${VENV_DIR}/bin/python" "${BACKEND_DIR}/manage.py" migrate --noinput

log "5/8 Collecting static files"
run_as_user env \
  DJANGO_SETTINGS_MODULE=smartclass.settings \
  SMARTCLASS_MODE=production \
  "${VENV_DIR}/bin/python" "${BACKEND_DIR}/manage.py" collectstatic --noinput

log "6/8 Creating/updating environment and service files"
run_sudo mkdir -p "${ENV_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  run_sudo tee "${ENV_FILE}" >/dev/null <<EOF
DJANGO_SETTINGS_MODULE=smartclass.settings
SMARTCLASS_MODE=production
PYTHONUNBUFFERED=1
DASHBOARD_MQTT_ENABLED=True
EOF
fi
run_sudo chmod 640 "${ENV_FILE}"
run_sudo chown root:"${RUN_GROUP}" "${ENV_FILE}"

run_sudo tee "/etc/systemd/system/${SERVICE_NAME}" >/dev/null <<EOF
[Unit]
Description=SmartClass Django ASGI Service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=-${ENV_FILE}
ExecStart=${VENV_DIR}/bin/daphne -b ${BIND_ADDR} -p ${BIND_PORT} smartclass.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

log "7/8 Reloading daemon and restarting ${SERVICE_NAME}"
run_sudo systemctl daemon-reload
run_sudo systemctl enable "${SERVICE_NAME}"
run_sudo systemctl restart "${SERVICE_NAME}"

log "8/8 Restarting daemon service (${DAEMON_SERVICE}) when present"
if systemctl list-unit-files "${DAEMON_SERVICE}" --no-legend 2>/dev/null | grep -q "${DAEMON_SERVICE}"; then
  run_sudo systemctl restart "${DAEMON_SERVICE}"
else
  log "Daemon service ${DAEMON_SERVICE} not found. Skipping."
fi

log "Deployment complete"
log "Service status:"
run_sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true

cat <<EOF

Done.
Main service: ${SERVICE_NAME}
Daemon service: ${DAEMON_SERVICE}
Useful commands:
  sudo systemctl status ${SERVICE_NAME}
  sudo journalctl -u ${SERVICE_NAME} -f

EOF
