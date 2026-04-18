#!/usr/bin/env bash
# =============================================================================
#  License Center Bot — Interactive Management Panel
# =============================================================================
set -Eeuo pipefail

REPO="https://github.com/beatrixbode5436/Lin.git"
APP_DIR="/opt/license-center"
SERVICE="license-center"
VENV_DIR="$APP_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
UNIT_FILE="/etc/systemd/system/${SERVICE}.service"
RUN_USER="${SUDO_USER:-root}"

# ── Colors ────────────────────────────────────────────────────────────────────
R='\033[31m'; G='\033[32m'; Y='\033[33m'; C='\033[36m'
B='\033[1m';  W='\033[97m'; N='\033[0m'

err()  { echo -e "${R}${B}[ERROR] $*${N}" >&2; exit 1; }
ok()   { echo -e "${G}${B}[OK] $*${N}"; }
info() { echo -e "${Y}[INFO] $*${N}"; }

# ── Header ────────────────────────────────────────────────────────────────────
header() {
  clear 2>/dev/null || true
  echo ""
  echo -e "${C}+======================================================+${N}"
  echo -e "${C}|${N}   ${B}${W}** License Center Bot -- Management Panel **${N}       ${C}|${N}"
  echo -e "${C}+======================================================+${N}"
  echo -e "${C}|${N}   ${B}${G}Developer:${N}  t.me/EmadHabibnia                   ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}Channel:${N}    @Emadhabibnia                        ${C}|${N}"
  echo -e "${C}+======================================================+${N}"
  echo ""
}

# ── Service status ────────────────────────────────────────────────────────────
get_status() {
  if systemctl is-active "$SERVICE" >/dev/null 2>&1; then
    echo -e "${G}${B}[ONLINE]${N}"
  else
    echo -e "${R}${B}[OFFLINE]${N}"
  fi
}

# ── Main menu ─────────────────────────────────────────────────────────────────
show_menu() {
  local status; status="$(get_status)"
  echo -e "${C}+------------------------------------------------------+${N}"
  echo -e "${C}|${N}   Status: $status"
  echo -e "${C}+------------------------------------------------------+${N}"
  echo -e "${C}|${N}   ${B}${G}1)${N}  Install / Reinstall                         ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}2)${N}  Update from GitHub                           ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}3)${N}  Edit config (.env)                           ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}4)${N}  Start                                        ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}5)${N}  Stop                                         ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}6)${N}  Restart                                      ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}7)${N}  Live logs                                    ${C}|${N}"
  echo -e "${C}|${N}   ${B}${G}8)${N}  Service status                               ${C}|${N}"
  echo -e "${C}+------------------------------------------------------+${N}"
  echo -e "${C}|${N}   ${B}${R}9)${N}  Remove service                               ${C}|${N}"
  echo -e "${C}+------------------------------------------------------+${N}"
  echo -e "${C}|${N}   ${B}${R}0)${N}  Exit                                         ${C}|${N}"
  echo -e "${C}+------------------------------------------------------+${N}"
}

# -- Helpers ───────────────────────────────────────────────────────────────────
check_root() {
  [[ $EUID -eq 0 ]] || err "Please run as root:  sudo bash install.sh"
}

install_prereqs() {
  info "Installing prerequisites (git, python3, venv)..."
  apt-get update -y -q
  apt-get install -y -q git python3 python3-venv python3-pip curl
  ok "Prerequisites installed"
}

clone_or_update_repo() {
  if [[ -d "$APP_DIR/.git" ]]; then
    info "Repository found — pulling latest..."
    git -C "$APP_DIR" fetch --all --prune
    git -C "$APP_DIR" reset --hard origin/main
  else
    [[ -d "$APP_DIR" ]] && rm -rf "$APP_DIR"
    info "Cloning repository..."
    git clone "$REPO" "$APP_DIR"
  fi
  [[ -f "$APP_DIR/main.py" ]]          || err "main.py not found after clone!"
  [[ -f "$APP_DIR/requirements.txt" ]] || err "requirements.txt not found after clone!"
  ok "Repository ready"
}

setup_venv() {
  info "Setting up Python virtual environment..."
  [[ -d "$VENV_DIR" ]] || python3 -m venv "$VENV_DIR"
  "$PIP" install --upgrade pip wheel -q
  "$PIP" install -r "$APP_DIR/requirements.txt" -q
  ok "Python environment ready"
}

configure_env() {
  [[ -f "$APP_DIR/.env" ]] || cp "$APP_DIR/env.example" "$APP_DIR/.env"

  echo ""
  echo -e "${C}+------------------------------------------------------+${N}"
  echo -e "${C}|${N}              Bot Configuration                       ${C}|${N}"
  echo -e "${C}+------------------------------------------------------+${N}"
  echo ""
  read -r -p "Bot Token: " INPUT_TOKEN
  INPUT_TOKEN="${INPUT_TOKEN// /}"
  [[ -n "$INPUT_TOKEN" ]] || err "Token cannot be empty"
  [[ "$INPUT_TOKEN" =~ ^[0-9]+:.+ ]] || err "Invalid token format. Example: 123456789:ABCdef..."

  echo ""
  echo -e "${Y}Get your numeric Telegram ID from @userinfobot.${N}"
  echo ""
  read -r -p "Admin IDs (numeric, comma-separated e.g. 123456,789012): " INPUT_ADMINS
  INPUT_ADMINS="${INPUT_ADMINS// /}"
  [[ "$INPUT_ADMINS" =~ ^[0-9]+(,[0-9]+)*$ ]] || err "Invalid admin ID format — numbers only"

  local default_url="http://$(hostname -I | awk '{print $1}'):5000"
  echo ""
  read -r -p "API Base URL [${default_url}]: " INPUT_URL
  INPUT_URL="${INPUT_URL:-$default_url}"

  sed -i "s|BOT_TOKEN=.*|BOT_TOKEN=${INPUT_TOKEN}|"     "$APP_DIR/.env"
  sed -i "s|ADMIN_IDS=.*|ADMIN_IDS=${INPUT_ADMINS}|"   "$APP_DIR/.env"
  sed -i "s|API_BASE_URL=.*|API_BASE_URL=${INPUT_URL}|" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"

  echo ""
  ok "Configuration saved"
}

create_service() {
  mkdir -p "$APP_DIR/data" "$APP_DIR/logs"
  cat > "$UNIT_FILE" <<EOF
[Unit]
Description=License Center Telegram Bot
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${PYTHON} ${APP_DIR}/main.py
Restart=always
RestartSec=5
StandardOutput=append:${APP_DIR}/logs/bot.log
StandardError=append:${APP_DIR}/logs/bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "$SERVICE" >/dev/null 2>&1 || true
  ok "Systemd service created"
}

# ── Actions ───────────────────────────────────────────────────────────────────

do_install() {
  check_root
  install_prereqs
  clone_or_update_repo
  setup_venv
  configure_env
  create_service
  systemctl restart "$SERVICE"
  echo ""
  echo -e "${G}+------------------------------------------------------+${N}"
  echo -e "${G}|${N}   Bot installed and started successfully!             ${G}|${N}"
  echo -e "${G}+------------------------------------------------------+${N}"
  echo ""
  systemctl status "$SERVICE" --no-pager -l || true
  echo ""
  read -r -p "Press Enter to continue..."
}

do_update() {
  check_root
  [[ -d "$APP_DIR/.git" ]] || err "Bot not installed. Run option 1 first."
  systemctl is-active --quiet "$SERVICE" 2>/dev/null && systemctl stop "$SERVICE" || true
  clone_or_update_repo
  setup_venv
  systemctl restart "$SERVICE"
  ok "Update complete — bot restarted!"
  echo ""
  read -r -p "Press Enter to continue..."
}

do_edit_config() {
  check_root
  [[ -f "$APP_DIR/.env" ]] || err ".env not found. Install first."
  local editor="${EDITOR:-$(command -v nano 2>/dev/null || command -v vi)}"
  "$editor" "$APP_DIR/.env"
  systemctl restart "$SERVICE" 2>/dev/null || true
  ok "Config saved — bot restarted"
  echo ""
  read -r -p "Press Enter to continue..."
}

do_start() {
  check_root
  systemctl start "$SERVICE" && ok "Bot started" || err "Failed to start"
  echo ""
  read -r -p "Press Enter to continue..."
}

do_stop() {
  check_root
  systemctl stop "$SERVICE" && ok "Bot stopped" || true
  echo ""
  read -r -p "Press Enter to continue..."
}

do_restart() {
  check_root
  systemctl restart "$SERVICE" && ok "Bot restarted" || err "Failed to restart"
  echo ""
  read -r -p "Press Enter to continue..."
}

do_logs() {
  echo -e "${Y}Press Ctrl+C to exit logs${N}"
  sleep 1
  local log_file="$APP_DIR/logs/bot.log"
  if [[ -f "$log_file" ]]; then
    tail -f "$log_file"
  else
    journalctl -u "$SERVICE" -f
  fi
}

do_status() {
  systemctl status "$SERVICE" --no-pager -l || true
  echo ""
  read -r -p "Press Enter to continue..."
}

do_remove() {
  check_root
  echo -e "${R}${B}WARNING: This will remove the service. Data files are kept.${N}"
  read -r -p "Confirm (yes/no): " confirm
  if [[ "$confirm" == "yes" ]]; then
    systemctl stop    "$SERVICE" 2>/dev/null || true
    systemctl disable "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT_FILE"
    systemctl daemon-reload
    ok "Service removed. Data still in $APP_DIR"
  else
    info "Cancelled"
  fi
  echo ""
  read -r -p "Press Enter to continue..."
}

# ── Main loop ─────────────────────────────────────────────────────────────────
main() {
  [[ -t 0 ]] || exec < /dev/tty
  check_root

  while true; do
    header
    show_menu
    read -r -p "$(echo -e "${C}License Center${N} ${B}>${N} option ${W}[0-9]${N}: ")" choice

    case "${choice:-}" in
      1) do_install     ;;
      2) do_update      ;;
      3) do_edit_config ;;
      4) do_start       ;;
      5) do_stop        ;;
      6) do_restart     ;;
      7) do_logs        ;;
      8) do_status      ;;
      9) do_remove      ;;
      0) echo "Goodbye!"; exit 0 ;;
      *) echo -e "${R}Invalid option${N}"; sleep 1 ;;
    esac
  done
}

main "$@"
