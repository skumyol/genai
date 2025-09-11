# Database Management Tools

This directory contains tools for managing the `maingamedata.db` SQLite database used by the medieval game application.

## Files

- `db_manager_script.py` - Main Python script with database management functionality
- `../manage_db.sh` - Convenient wrapper script for running from project root

## Database Structure

The `maingamedata.db` contains the following main tables:

- **main_game_data** - Top-level game data per user
- **sessions** - Game sessions with settings and metadata
- **days** - Daily game data within sessions
- **dialogues** - Conversations between NPCs
- **messages** - Individual messages within dialogues
- **npc_memories** - NPC memory and state data
- **users** - User account information
- **user_events** - User activity tracking
- **session_metrics** - Session performance metrics
- **session_imports** - Import tracking data

## Usage

### From Project Root (Recommended)

```bash
# Show database statistics
./manage_db.sh stats

# List all entries
./manage_db.sh list

# List entries from specific table with limit
./manage_db.sh list --table sessions --limit 10

# Show table schemas
./manage_db.sh schema

# Show specific table schema
./manage_db.sh schema --table messages

# Clean database (with confirmation)
./manage_db.sh clean

# Clean database (force, no confirmation)
./manage_db.sh clean --force

# Vacuum database to reclaim space
./manage_db.sh vacuum
```

### Direct Script Usage

```bash
cd backend
python3 db_manager_script.py --help

# Examples:
python3 db_manager_script.py stats
python3 db_manager_script.py list --table users
python3 db_manager_script.py clean --force
python3 db_manager_script.py schema --table dialogues
```

## Available Commands

### `list`
Lists entries from database tables. Shows table contents in a formatted view.

Options:
- `--table <name>` - Show only specific table
- `--limit <num>` - Limit number of rows displayed

### `clean`
Deletes all data from the database while preserving table structure.

Options:
- `--force` - Skip confirmation prompt

**⚠️ WARNING**: This permanently deletes all game data!

### `stats`
Shows database statistics including:
- Database file size
- Row counts per table
- Column counts per table
- Total row count

### `schema`
Shows detailed table schema information including:
- Column definitions (name, type, constraints)
- Primary keys
- Foreign key relationships
- Indexes

Options:
- `--table <name>` - Show only specific table schema

### `vacuum`
Runs SQLite VACUUM command to:
- Reclaim unused space
- Defragment database file
- Optimize storage

## Safety Features

- **Confirmation prompts** for destructive operations
- **Foreign key constraint handling** during cleaning
- **Transaction rollback** on errors
- **Read-only operations** for listing and stats
- **Timeout handling** for database locks

## Example Output

### Stats Command
```
============================================================
DATABASE STATISTICS
============================================================
Database path: /path/to/maingamedata.db
Database size: 124.00 KB

Table                     Rows       Columns   
---------------------------------------------
sessions                  5          11        
messages                  142        8         
dialogues                 23         13        
...
---------------------------------------------
TOTAL                     170
```

### Schema Command
```
============================================================
SCHEMA: sessions
============================================================
Column               Type            NotNull  Default         PK 
-----------------------------------------------------------------
session_id           TEXT            0                        1  
created_at           TEXT            1                        0  
current_day          INTEGER         1                        0  
...

Foreign Keys:
  None

Indexes:
  idx_sessions_game (unique: False)
```

## Integration

These tools integrate with the main application's `DatabaseManager` class and use the same database connection patterns and schema definitions.

## Development

The script is designed to be:
- **Safe** - Multiple confirmation steps for destructive operations
- **Informative** - Detailed output and error messages
- **Flexible** - Multiple ways to filter and limit output
- **Maintainable** - Clear code structure and comprehensive error handling

## Troubleshooting

### Database Locked
If you get "database is locked" errors:
- Stop any running application instances
- Wait for background processes to complete
- The script uses 30-second timeouts to handle locks

### Permission Errors
Ensure the script has read/write permissions:
```bash
chmod +x manage_db.sh
chmod +x backend/db_manager_script.py
```

### Python Version
The script requires Python 3.6+ with SQLite3 support (included in standard library).
