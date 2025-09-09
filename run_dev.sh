#!/usr/bin/env sh
set -e

# Install deps if missing
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting dev server..."
exec npm run dev
