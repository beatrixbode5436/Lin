#!/usr/bin/env bash
# =============================================================================
#  License Center Bot – install.sh
#  Usage: sudo bash install.sh [command]
#
#  Commands:
#    install      First-time setup (venv, deps, .env, systemd service)
#    update       Pull latest changes, reinstall deps, restart
#    restart      Restart the systemd service
#    stop         Stop the service
#    status       Show service status
#    logs         Follow live log output
#    remove       Remove the systemd service (data kept)
#    edit-config  Open .env in editor
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/beatrixbode5436/Lin"
SERVICE="license-center"
INSTALL_DIR="/opt/license-center"
APP_DIR="$INSTALL_DIR"
VENV_DIR="$APP_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
UNIT_FILE="/etc/systemd/system/${SERVICE}.service"
RUN_USER="${SUDO_USER:-$(whoami)}"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

need_root() {
    [[ $EUID -eq 0 ]] || error "This command requires root. Run: sudo bash install.sh $1"
}

# ── Sub-commands ──────────────────────────────────────────────────────────────

cmd_install() {
    need_root "install"
    info "=== Installing License Center Bot ==="

    # Clone or update repo
    if [[ -d "$APP_DIR/.git" ]]; then
        info "Repo already exists, pulling latest…"
        git -C "$APP_DIR" pull --ff-only
    else
        # Remove leftover directory from a previous failed install
        if [[ -d "$APP_DIR" ]]; then
            info "Removing incomplete directory…"
            rm -rf "$APP_DIR"
        fi
        info "Cloning repository…"
        git clone "$REPO_URL" "$APP_DIR"
    fi

    # Create data directories (not tracked by git)
    mkdir -p "$APP_DIR/data" "$APP_DIR/logs"
    info "Directories: data/ logs/ created"

    # Virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        python3 -m venv "$VENV_DIR"
        info "Virtual environment created"
    else
        info "Virtual environment already exists"
    fi

    # Dependencies
    "$PIP" install --upgrade pip -q
    "$PIP" install -r "$APP_DIR/requirements.txt" -q
    info "Dependencies installed"

    # .env file
    if [[ ! -f "$APP_DIR/.env" ]]; then
        cp "$APP_DIR/env.example" "$APP_DIR/.env"
        warn ".env created from template – edit it before starting:"
        warn "  sudo bash install.sh edit-config"
    else
        info ".env already exists"
    fi

    # systemd unit
    cat > "$UNIT_FILE" <<EOF
[Unit]
Description=License Center Telegram Bot
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${PYTHON} ${APP_DIR}/main.py
Restart=always
RestartSec=10
StandardOutput=append:${APP_DIR}/logs/bot.log
StandardError=append:${APP_DIR}/logs/bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE"
    info "systemd service created and enabled: $SERVICE"

    echo ""
    info "=== Installation complete! ==="
    warn "Next steps:"
    warn "  1. Edit config:  sudo bash install.sh edit-config"
    warn "  2. Start bot:    sudo bash install.sh restart"
}

cmd_update() {
    need_root "update"
    info "=== Updating License Center Bot ==="

    systemctl is-active --quiet "$SERVICE" && systemctl stop "$SERVICE" && info "Service stopped"

    "$PIP" install --upgrade pip -q
    "$PIP" install -r "$APP_DIR/requirements.txt" -q
    info "Dependencies updated"

    systemctl start "$SERVICE"
    info "=== Update complete! ==="
}

cmd_restart() {
    need_root "restart"
    systemctl restart "$SERVICE"
    info "Service restarted"
}

cmd_stop() {
    need_root "stop"
    systemctl stop "$SERVICE"
    info "Service stopped"
}

cmd_status() {
    systemctl status "$SERVICE" --no-pager || true
}

cmd_logs() {
    local log_file="$APP_DIR/logs/bot.log"
    if [[ -f "$log_file" ]]; then
        tail -f "$log_file"
    else
        journalctl -u "$SERVICE" -f
    fi
}

cmd_remove() {
    need_root "remove"
    warn "This will remove the systemd service. Data files will NOT be deleted."
    read -rp "Are you sure? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        systemctl stop    "$SERVICE" 2>/dev/null || true
        systemctl disable "$SERVICE" 2>/dev/null || true
        rm -f "$UNIT_FILE"
        systemctl daemon-reload
        info "Service removed. Data is still in $APP_DIR"
    else
        info "Removal cancelled"
    fi
}

cmd_edit_config() {
    local editor
    editor="${EDITOR:-$(command -v nano 2>/dev/null || command -v vi)}"
    "$editor" "$APP_DIR/.env"
}

cmd_help() {
    cat <<EOF
Usage: sudo bash install.sh [command]

Commands:
  install      First-time setup (venv, deps, .env, systemd)
  update       Reinstall deps and restart service
  restart      Restart the service
  stop         Stop the service
  status       Show service status
  logs         Follow live logs
  remove       Remove systemd service (keeps data)
  edit-config  Edit .env config file
EOF
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-help}" in
    install)     cmd_install     ;;
    update)      cmd_update      ;;
    restart)     cmd_restart     ;;
    stop)        cmd_stop        ;;
    status)      cmd_status      ;;
    logs)        cmd_logs        ;;
    remove)      cmd_remove      ;;
    edit-config) cmd_edit_config ;;
    help|--help|-h) cmd_help    ;;
    *) error "Unknown command: $1. Run: bash install.sh help" ;;
esac
