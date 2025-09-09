#!/bin/bash
# Reset the database from default_settings.json

# Navigate to script directory
cd "$(dirname "$0")"

# Delete existing database in databases folder
mkdir -p databases
rm -f databases/checkpoints.db

# Restart API to reinitialize database
./run_api.sh
