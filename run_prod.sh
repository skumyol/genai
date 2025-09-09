#!/usr/bin/env sh
set -e

PORT=${PORT:-5173}

if [ "$1" = "--check" ]; then
  echo "Checking if preview is running on port $PORT..."
  if lsof -i tcp:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Server is running on port $PORT."
    exit 0
  else
    echo "No server listening on port $PORT."
    exit 1
  fi
fi

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Building..."
npm run build

echo "Starting preview on port $PORT..."
exec npm run preview -- --port $PORT
