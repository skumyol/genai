#!/usr/bin/env bash
set -euo pipefail

# Run a single experiment from a config for N days (default 2) to sanity check.
# Usage: ./run_one_experiment.sh <experiment_name> [days] [--continue-from-day=N]
#        ./run_one_experiment.sh <experiment_name> [days] [--continue-from=session_id:day]

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"
BASE_CONFIG="$SCRIPT_DIR/experimental_config_six.json"
CHECKPOINT_DB="$SCRIPT_DIR/databases/checkpoints.db"

EXP_NAME=${1:-}
DAYS=${10:-10}
CONTINUE_FROM_DAY=""
CONTINUE_FROM_SESSION=""

# Parse additional arguments for continue functionality
for arg in "${@:3}"; do
  case $arg in
    --continue-from-day=*)
      CONTINUE_FROM_DAY="${arg#*=}"
      shift
      ;;
    --continue-from=*)
      CONTINUE_FROM="${arg#*=}"
      if [[ "$CONTINUE_FROM" == *":"* ]]; then
        CONTINUE_FROM_SESSION="${CONTINUE_FROM%:*}"
        CONTINUE_FROM_DAY="${CONTINUE_FROM#*:}"
      else
        CONTINUE_FROM_DAY="$CONTINUE_FROM"
      fi
      shift
      ;;
    *)
      ;;
  esac
done

# Function to list available checkpoints for a session
list_checkpoints() {
  local session_id="$1"
  if [ ! -f "$CHECKPOINT_DB" ]; then
    echo "No checkpoint database found at $CHECKPOINT_DB" >&2
    return 1
  fi
  
  echo "Available checkpoints for session '$session_id':"
  sqlite3 "$CHECKPOINT_DB" "
    SELECT DISTINCT day 
    FROM days
    WHERE session_id = '$session_id'
    ORDER BY day;
  " 2>/dev/null || {
    echo "No checkpoints found or database query failed" >&2
    return 1
  }
}

# Function to find available sessions for an experiment
find_experiment_sessions() {
  local exp_name="$1"
  if [ ! -f "$CHECKPOINT_DB" ]; then
    return 1
  fi
  
  echo "Available sessions for experiment '$exp_name':"
  echo "Format: session_id | current_day | max_day_with_checkpoints"
  sqlite3 "$CHECKPOINT_DB" "
    SELECT s.session_id || ' | ' || s.current_day || ' | ' || COALESCE(MAX(d.day), 'no checkpoints')
    FROM sessions s
    LEFT JOIN days d ON s.session_id = d.session_id
    WHERE s.session_id LIKE '$exp_name%'
    GROUP BY s.session_id, s.current_day
    ORDER BY s.session_id;
  " 2>/dev/null || {
    echo "No sessions found or database query failed" >&2
    return 1
  }
}

# Function to validate checkpoint exists
validate_checkpoint() {
  local session_id="$1"
  local day="$2"
  
  if [ ! -f "$CHECKPOINT_DB" ]; then
    echo "Checkpoint database not found: $CHECKPOINT_DB" >&2
    return 1
  fi
  
  local count
  count=$(sqlite3 "$CHECKPOINT_DB" "
    SELECT COUNT(*) 
    FROM days
    WHERE session_id = '$session_id' AND day = $day;
  " 2>/dev/null) || {
    echo "Error querying checkpoint database" >&2
    return 1
  }
  
  if [ "$count" -eq 0 ]; then
    echo "No checkpoint found for session '$session_id' at day $day" >&2
    echo "Available checkpoints:" >&2
    list_checkpoints "$session_id" >&2
    return 1
  fi
  
  return 0
}

if [ -z "$EXP_NAME" ]; then
  echo "Usage: $0 <experiment_name> [days] [--continue-from-day=N] [--continue-from=session_id:day]" >&2
  echo "Examples: exp_gpt5_all | exp_qwen8b_all | exp_mixed_social_1b_game_8b" >&2
  echo "Continue examples:" >&2
  echo "  $0 exp_mixed_social_1b_game_8b 10 --continue-from-day=5" >&2
  echo "  $0 exp_mixed_social_1b_game_8b 10 --continue-from=exp_mixed_social_1b_game_8b_mixed_rep_on:5" >&2
  echo "" >&2
  echo "To see available checkpoints, use:" >&2
  echo "  $0 --list-checkpoints <experiment_name>" >&2
  exit 1
fi

# Handle special case for listing checkpoints
if [ "$EXP_NAME" = "--list-checkpoints" ]; then
  if [ -z "$2" ]; then
    echo "Usage: $0 --list-checkpoints <experiment_name>" >&2
    exit 1
  fi
  EXPERIMENT_TO_LIST="$2"
  echo "Listing checkpoints for experiment: $EXPERIMENT_TO_LIST"
  echo ""
  
  # Check if experiment sessions exist
  result=$(sqlite3 "$CHECKPOINT_DB" "
    SELECT COUNT(*)
    FROM sessions s
    WHERE s.session_id LIKE '$EXPERIMENT_TO_LIST%'
  " 2>/dev/null || echo "0")
  
  if [ "$result" -gt 0 ]; then
    find_experiment_sessions "$EXPERIMENT_TO_LIST"
    echo ""
    echo "To see detailed checkpoints for a specific session, run:"
    echo "  sqlite3 $CHECKPOINT_DB \"SELECT DISTINCT day FROM days WHERE session_id = 'session_id_here' ORDER BY day;\""
  else
    echo "No sessions found for experiment '$EXPERIMENT_TO_LIST'"
    echo "Available experiments in database:"
    sqlite3 "$CHECKPOINT_DB" "SELECT DISTINCT substr(session_id, 1, instr(session_id || '_', '_') - 1) FROM sessions;" 2>/dev/null || echo "None"
  fi
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required to override duration_days" >&2
  exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Error: sqlite3 is required for checkpoint operations" >&2
  exit 1
fi

if [ ! -f "$BASE_CONFIG" ]; then
  echo "Config not found: $BASE_CONFIG" >&2
  exit 1
fi

# Load .env if present to populate API keys and config
if [ -f "$SCRIPT_DIR/.env" ]; then
  echo "Loading environment from $SCRIPT_DIR/.env"
  set -a
  # shellcheck disable=SC1090
  . "$SCRIPT_DIR/.env"
  set +a
fi

# Prepare environment
PY=${PYTHON:-python3}
if ! $PY -c "import sys; print(sys.version)" >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  $PY -m venv "$VENV_DIR"
fi
. "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null

# Create a temporary config with days overridden
TMP_CONFIG=$(mktemp)
jq ".session_config.duration_days=$DAYS" "$BASE_CONFIG" > "$TMP_CONFIG"

# Handle continue functionality
if [ -n "$CONTINUE_FROM_DAY" ]; then
  echo "Continue mode: Starting from day $CONTINUE_FROM_DAY"
  
  # If specific session provided, validate it
  if [ -n "$CONTINUE_FROM_SESSION" ]; then
    echo "Using specific session: $CONTINUE_FROM_SESSION"
    if ! validate_checkpoint "$CONTINUE_FROM_SESSION" "$CONTINUE_FROM_DAY"; then
      exit 1
    fi
    SELECTED_SESSION="$CONTINUE_FROM_SESSION"
  else
    # Auto-discover sessions for this experiment
    echo "Auto-discovering sessions for experiment '$EXP_NAME'..."
    
    if ! find_experiment_sessions "$EXP_NAME" >/dev/null 2>&1; then
      echo "No existing sessions found for experiment '$EXP_NAME'. Run without --continue first." >&2
      exit 1
    fi
    
    # Try to find a session that has the requested day
    FOUND_SESSION=""
    while IFS='|' read -r session_id current_day max_day; do
      if [ -n "$session_id" ] && [ -n "$max_day" ] && [ "$max_day" -ge "$CONTINUE_FROM_DAY" ]; then
        if validate_checkpoint "$session_id" "$CONTINUE_FROM_DAY" >/dev/null 2>&1; then
          FOUND_SESSION="$session_id"
          break
        fi
      fi
    done < <(sqlite3 "$CHECKPOINT_DB" "
      SELECT s.session_id || '|' || s.current_day || '|' || COALESCE(MAX(d.day), s.current_day)
      FROM sessions s
      LEFT JOIN days d ON s.session_id = d.session_id
      WHERE s.session_id LIKE '$EXP_NAME%'
      GROUP BY s.session_id, s.current_day
      ORDER BY s.session_id;
    " 2>/dev/null || echo "")
    
    if [ -z "$FOUND_SESSION" ]; then
      echo "No session found with checkpoint at day $CONTINUE_FROM_DAY" >&2
      echo "Available sessions:" >&2
      find_experiment_sessions "$EXP_NAME" >&2
      exit 1
    fi
    
    SELECTED_SESSION="$FOUND_SESSION"
    echo "Found session with checkpoint: $SELECTED_SESSION"
  fi
  
  # Update config to include continue information
  jq ".session_config.continue_from_day=$CONTINUE_FROM_DAY | .session_config.continue_from_session=\"$SELECTED_SESSION\"" "$TMP_CONFIG" > "$TMP_CONFIG.tmp"
  mv "$TMP_CONFIG.tmp" "$TMP_CONFIG"
  
  echo "Continuing experiment '$EXP_NAME' from day $CONTINUE_FROM_DAY using session '$SELECTED_SESSION'"
else
  echo "Running experiment '$EXP_NAME' for $DAYS day(s) from the beginning"
fi

echo "Using temporary config: $TMP_CONFIG"

# Optional providers
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://213.136.69.184:11434}"
export LLM_LOCAL_TIMEOUT_SECONDS="${LLM_LOCAL_TIMEOUT_SECONDS:-20}"
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "Warning: OPENROUTER_API_KEY not set; OpenRouter models will fail." >&2
fi

# Preflight for only this experiment
echo "Preflight: verifying LLM endpoints for $EXP_NAME..."
$PY "$SCRIPT_DIR/llm_preflight.py" --config "$TMP_CONFIG" --experiment "$EXP_NAME"

# Clean previous metrics/results for deterministic reruns
if command -v jq >/dev/null 2>&1; then
  # Portable alternative to 'mapfile' for macOS bash 3.2
  while IFS= read -r sid; do
    [ -n "$sid" ] || continue
    rm -f "$SCRIPT_DIR/metrics"/*"_${sid}_metrics."* || true
  done < <(jq -r ".experiments.\"$EXP_NAME\".variants[].config.session_id" "$TMP_CONFIG" 2>/dev/null | sed '/^null$/d')
else
  rm -f "$SCRIPT_DIR/metrics/${EXP_NAME}"*
fi
rm -f "$SCRIPT_DIR/experiment_results_${EXP_NAME}_"*.json

# Run and analyze
if [ -n "$CONTINUE_FROM_DAY" ]; then
  # Use the enhanced runner for continue functionality
  $PY "$SCRIPT_DIR/runner_with_continue.py" --config "$TMP_CONFIG" --experiment "$EXP_NAME" --continue-from-day "$CONTINUE_FROM_DAY" ${CONTINUE_FROM_SESSION:+--continue-from-session "$CONTINUE_FROM_SESSION"}
else
  # Use the original runner for normal runs
  $PY "$SCRIPT_DIR/runner.py" --config "$TMP_CONFIG" --experiment "$EXP_NAME"
fi

$PY "$SCRIPT_DIR/analyze_experiments.py" --experiment "$EXP_NAME" --metrics "$SCRIPT_DIR/metrics" --out "$SCRIPT_DIR/metrics/analysis_${EXP_NAME}.json"

# Cleanup temporary config
rm -f "$TMP_CONFIG"

echo "Experiment completed successfully!"
if [ -n "$CONTINUE_FROM_DAY" ]; then
  echo "Continued from day $CONTINUE_FROM_DAY"
fi
