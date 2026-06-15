#!/usr/bin/env bash
set -euo pipefail

# Smart Classroom Linux installer
# - Installs system dependencies (APT-based distros)
# - Creates Python virtual environment
# - Installs Python requirements
# - Runs migrations and collectstatic
# - Creates and enables systemd service (auto-start on reboot)

APP_NAME="${APP_NAME:-smartclass}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
BACKEND_DIR="${BACKEND_DIR:-${PROJECT_ROOT}/backend}"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BIND_ADDR="${BIND_ADDR:-0.0.0.0}"
BIND_PORT="${BIND_PORT:-8001}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}.service}"
RUN_USER="${RUN_USER:-${SUDO_USER:-$USER}}"
RUN_GROUP="${RUN_GROUP:-$(id -gn "${RUN_USER}")}"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "ERROR: Backend directory not found: ${BACKEND_DIR}"
  exit 1
fi

if [[ ! -f "${BACKEND_DIR}/requirements.txt" ]]; then
  echo "ERROR: requirements.txt not found in ${BACKEND_DIR}"
  exit 1
fi

if [[ ! -f "${BACKEND_DIR}/manage.py" ]]; then
  echo "ERROR: manage.py not found in ${BACKEND_DIR}"
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "Re-running with sudo to install packages and systemd service..."
  exec sudo -E bash "$0" "$@"
fi

echo "[1/7] Installing OS dependencies..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    libpq-dev \
    pkg-config
else
  echo "WARNING: apt-get not found. Skipping OS package install."
  echo "Please ensure Python, venv, and build tools are installed manually."
fi

echo "[2/7] Preparing virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u "${RUN_USER}" "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

sudo -u "${RUN_USER}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel
sudo -u "${RUN_USER}" "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

echo "[3/7] Running Django migrations..."
cd "${BACKEND_DIR}"
sudo -u "${RUN_USER}" env \
  DJANGO_SETTINGS_MODULE=smartclass.settings \
  SMARTCLASS_MODE=production \
  "${VENV_DIR}/bin/python" manage.py migrate --noinput

echo "[4/7] Collecting static files..."
sudo -u "${RUN_USER}" env \
  DJANGO_SETTINGS_MODULE=smartclass.settings \
  SMARTCLASS_MODE=production \
  "${VENV_DIR}/bin/python" manage.py collectstatic --noinput

echo "[5/7] Creating systemd service: ${SERVICE_NAME}"
cat >/etc/systemd/system/${SERVICE_NAME} <<EOF
[Unit]
Description=Smart Classroom Django ASGI Service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${BACKEND_DIR}
Environment=DJANGO_SETTINGS_MODULE=smartclass.settings
Environment=SMARTCLASS_MODE=production
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/daphne -b ${BIND_ADDR} -p ${BIND_PORT} smartclass.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "[6/7] Enabling and starting service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[7/7] Checking status..."
systemctl --no-pager --full status "${SERVICE_NAME}" || true

echo
echo "Installation completed."
echo "Service name: ${SERVICE_NAME}"
echo "App URL: http://<server-ip>:${BIND_PORT}"
echo
echo "Useful commands:"
echo "  sudo systemctl restart ${SERVICE_NAME}"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo
echo "Optional first-time setup:"
echo "  cd ${BACKEND_DIR}"
echo "  ${VENV_DIR}/bin/python manage.py createsuperuser"
