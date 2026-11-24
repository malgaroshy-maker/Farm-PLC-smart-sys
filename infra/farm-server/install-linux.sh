#!/usr/bin/env sh
# Algaroshy Farm server for Linux (Milestone G7): a systemd service that starts the farm app at boot
# and restarts it if it stops. Runs as the user who calls sudo, from this project folder.
#
#   sudo sh infra/farm-server/install-linux.sh             install + start
#   sudo sh infra/farm-server/install-linux.sh --uninstall remove
#
# Run ./run.sh demo once by hand first: it sets up Python, packages and .env.
# Logs: journalctl -u algaroshy-farm -f   and   logs/farm-server.log
set -eu

UNIT=algaroshy-farm
UNIT_FILE=/etc/systemd/system/$UNIT.service
ROOT=$(cd "$(dirname "$0")/../.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
  echo "[!] Run with sudo: sudo sh infra/farm-server/install-linux.sh"
  exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
  systemctl disable --now "$UNIT" 2>/dev/null || true
  rm -f "$UNIT_FILE"
  systemctl daemon-reload
  echo "Removed the $UNIT service."
  exit 0
fi

RUN_USER=${SUDO_USER:-}
if [ -z "$RUN_USER" ] || [ "$RUN_USER" = "root" ]; then
  echo "[!] Call this with sudo from the user account that owns the project (not as root)."
  exit 1
fi
USER_PATH=$(su - "$RUN_USER" -c 'printf %s "$PATH"')
NODE=$(su - "$RUN_USER" -c 'command -v node' || true)
if [ -z "$NODE" ]; then
  echo "[!] Node.js 20+ is required for $RUN_USER: https://nodejs.org"
  exit 1
fi
if [ ! -f "$ROOT/.env" ] || [ ! -d "$ROOT/apps/api/.venv" ]; then
  echo "[!] Run ./run.sh demo once first (it sets up Python, packages and .env), then run this again."
  exit 1
fi

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Algaroshy Farm irrigation server (API, controller link, web app)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$ROOT
Environment=PATH=$USER_PATH
ExecStart=$NODE scripts/start.mjs server
Restart=always
RestartSec=10
# the launcher stops its child processes itself on SIGTERM
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$UNIT"
echo "Installed and started $UNIT. First start builds the web app; then open http://localhost:4173"
echo "Status: systemctl status $UNIT    Logs: journalctl -u $UNIT -f"
