#!/bin/bash
#
# Wrapper script for database management
# Usage from project root:
#   ./manage_db.sh list
#   ./manage_db.sh clean
#   ./manage_db.sh stats
#   ./manage_db.sh schema
#

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
DB_SCRIPT="$BACKEND_DIR/db_manager_script.py"

# Check if the database script exists
if [ ! -f "$DB_SCRIPT" ]; then
    echo "Error: Database script not found at $DB_SCRIPT"
    exit 1
fi

# Change to backend directory and run the script
cd "$BACKEND_DIR"
python3 db_manager_script.py "$@"
