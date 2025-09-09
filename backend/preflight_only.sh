#!/usr/bin/env bash
set -euo pipefail

# Preflight-only runner for experiment configs.
# Usage: ./preflight_only.sh [--experiment EXP] [--force-test]

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"
CONFIG="$SCRIPT_DIR/experimental_config_six.json"

EXP_FILTER=""
FORCE_TEST=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --experiment)
      EXP_FILTER="$2"; shift 2 ;;
    --force-test)
      FORCE_TEST=1; shift ;;
    *)
      echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$SCRIPT_DIR/.env"
  set +a
fi

PY=${PYTHON:-python3}
if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi
. "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null

if [ $FORCE_TEST -eq 1 ]; then
  export LLM_FORCE_TEST_PROVIDER=1
  echo "[Preflight] Forcing test provider to avoid network calls."
fi

if [ -n "$EXP_FILTER" ]; then
  echo "Running preflight for experiment: $EXP_FILTER"
  exec $PY "$SCRIPT_DIR/llm_preflight.py" --config "$CONFIG" --experiment "$EXP_FILTER"
else
  echo "Running preflight for all experiments defined in: $CONFIG"
  exec $PY "$SCRIPT_DIR/llm_preflight.py" --config "$CONFIG"
fi

