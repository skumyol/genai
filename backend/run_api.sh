#!/usr/bin/env sh
set -e

PORT=${API_PORT:-8000}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"

if [ "$1" = "--check" ]; then
  echo "Checking if backend is running on port $PORT..."
  if lsof -i tcp:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Backend is running on port $PORT."
    exit 0
  else
    echo "No backend listening on port $PORT."
    exit 1
  fi
fi

# Prefer system Python, then fallback
PY=${PYTHON:-python3}

if ! $PY -c "import sys; print(sys.version)" >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  $PY -m venv "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$SCRIPT_DIR/requirements.txt"

export API_PORT=$PORT
exec $PY "$SCRIPT_DIR/app.py"
