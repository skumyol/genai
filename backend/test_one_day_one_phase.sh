#!/usr/bin/env bash
set -euo pipefail

# Run a single experiment for exactly 1 day and 1 phase, then analyze metrics.
# Usage: ./test_one_day_one_phase.sh <experiment_name> [phase]
# Example phases: MORNING | NOON | AFTERNOON | EVENING | NIGHT

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"
BASE_CONFIG="$SCRIPT_DIR/experimental_config_six.json"

EXP_NAME=${1:-}
ONE_PHASE=${2:-NOON}

if [ -z "$EXP_NAME" ]; then
  echo "Usage: $0 <experiment_name> [phase]" >&2
  echo "Examples: exp_gpt5_all | exp_qwen8b_all | exp_mixed_social_1b_game_8b" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required to construct single-phase config" >&2
  exit 1
fi

# Load .env if present to populate API keys and config
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$SCRIPT_DIR/.env"
  set +a
fi

PY=${PYTHON:-python3}
if ! $PY -c "import sys; print(sys.version)" >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi
. "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null

# Create a temporary config: 1 day, 1 phase
TMP_CONFIG=$(mktemp)
jq \
  --arg phase "$ONE_PHASE" \
  '.session_config.duration_days=1 | .session_config.time_periods_per_day=[ $phase ]' \
  "$BASE_CONFIG" > "$TMP_CONFIG"

echo "Testing experiment '$EXP_NAME' for 1 day and phase '$ONE_PHASE'"

# Preflight for this experiment
$PY "$SCRIPT_DIR/llm_preflight.py" --config "$TMP_CONFIG" --experiment "$EXP_NAME"

# Clean previous metrics for this experiment's fixed session IDs
jq -r ".experiments.\"$EXP_NAME\".variants[].config.session_id" "$TMP_CONFIG" 2>/dev/null | sed '/^null$/d' | while read sid; do
  rm -f "$SCRIPT_DIR/metrics"/*"_${sid}_metrics."* || true
done
rm -f "$SCRIPT_DIR/experiment_results_${EXP_NAME}_"*.json

# Run the experiment
$PY "$SCRIPT_DIR/runner.py" --config "$TMP_CONFIG" --experiment "$EXP_NAME"

# Analyze output and save a deterministic analysis file
OUT_JSON="$SCRIPT_DIR/metrics/analysis_${EXP_NAME}_one_phase.json"
$PY "$SCRIPT_DIR/analyze_experiments.py" --experiment "$EXP_NAME" --metrics "$SCRIPT_DIR/metrics" --out "$OUT_JSON"

echo "\nAnalysis summary (key metrics):"
if command -v jq >/dev/null 2>&1; then
  jq '{generated_at, groups}' "$OUT_JSON"
else
  echo "Analysis saved to $OUT_JSON"
fi

echo "\nDone. Metrics are under backend/metrics; log: backend/experimental_run.log"
