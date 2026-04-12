#!/usr/bin/env bash
# Idempotent helper: venv + editable install; optional systemd unit copy (root only).
# Does not contain secrets. Paths are derived from this script's location.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INSTALL_DEV=0
COPY_SYSTEMD=0

usage() {
  echo "Usage: $0 [--dev] [--install-systemd]"
  echo "  Run as normal user: creates .venv and pip install -e ."
  echo "  --dev             pip install -e \".[dev]\" (pytest, ruff, mypy)"
  echo "  --install-systemd run with sudo: copy deploy/*.service and deploy/*.timer to /etc/systemd/system/ and daemon-reload (venv step skipped)"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev) INSTALL_DEV=1 ;;
    --install-systemd) COPY_SYSTEMD=1 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

if [[ "$COPY_SYSTEMD" -eq 1 ]]; then
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Use root only for unit install: sudo $0 --install-systemd" >&2
    exit 1
  fi
  install -m 0644 "$REPO_ROOT/deploy/habr-tech-radar.service" /etc/systemd/system/
  install -m 0644 "$REPO_ROOT/deploy/habr-tech-radar.timer" /etc/systemd/system/
  chmod +x "$REPO_ROOT/deploy/run_once.sh"
  systemctl daemon-reload
  echo "Installed units from $REPO_ROOT/deploy/"
  echo "Ensure lock dir exists (default lock: /var/lib/habr-tech-radar/pipeline.lock):"
  echo "  sudo mkdir -p /var/lib/habr-tech-radar && sudo chown htrbot:htrbot /var/lib/habr-tech-radar"
  echo "(replace htrbot with your service user if different)"
  echo "Enable timer: systemctl enable --now habr-tech-radar.timer"
  exit 0
fi

cd "$REPO_ROOT"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "python3.12 not found in PATH. Install Python 3.12 (e.g. apt install python3.12 python3.12-venv on Ubuntu)." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ "$INSTALL_DEV" -eq 1 ]]; then
  pip install -e ".[dev]"
else
  pip install -e .
fi

echo ""
echo "Repo:     $REPO_ROOT"
echo "Venv:     $REPO_ROOT/.venv"
echo "Activate: source $REPO_ROOT/.venv/bin/activate"
echo "Config:   copy .env.example to $REPO_ROOT/.env and edit (no secrets in git)."
echo "Run once: $REPO_ROOT/.venv/bin/habr-tech-radar"
echo "systemd uses: $REPO_ROOT/deploy/run_once.sh (flock; chmod +x if needed)"
echo ""
echo "systemd: edit deploy/habr-tech-radar.service and deploy/habr-tech-radar.timer paths, then:"
echo "  sudo $REPO_ROOT/deploy/install_vm.sh --install-systemd"
