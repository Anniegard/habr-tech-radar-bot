#!/usr/bin/env bash
# One-shot pipeline with non-overlapping runs via flock (systemd ExecStart).
# If another instance holds the lock, log to stderr and exit 0 (not a failure).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin/habr-tech-radar"

# Override in systemd unit: Environment=HTR_PIPELINE_LOCK_FILE=/path/to/pipeline.lock
LOCK_FILE="${HTR_PIPELINE_LOCK_FILE:-/var/lib/habr-tech-radar/pipeline.lock}"

if [[ ! -x "$VENV_BIN" ]]; then
  echo "habr-tech-radar: error: missing venv entrypoint: $VENV_BIN" >&2
  exit 1
fi

exec 9>>"$LOCK_FILE"
if ! flock -n 9; then
  echo "habr-tech-radar: skip: overlap lock_held path=$LOCK_FILE" >&2
  exit 0
fi

exec "$VENV_BIN" "$@"
