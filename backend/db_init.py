"""
Function to initialize main_game_data table in the database.
"""
import sqlite3
import os
import json
from datetime import datetime

def init_main_game_data(db_path, default_settings_path=None, agent_settings_path=None):
    """
    Initialize the main_game_data table with default values if needed.
    
    This ensures that the database has the necessary baseline data for proper operation.
    """
    if not default_settings_path:
        default_settings_path = os.path.join(os.path.dirname(__file__), 'default_settings.json')
    
    if not agent_settings_path:
        agent_settings_path = os.path.join(os.path.dirname(__file__), 'agent_settings.json')
        
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='main_game_data'")
        if not cursor.fetchone():
            # Create the table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS main_game_data (
                    user_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    default_settings_path TEXT NOT NULL,
                    agent_settings_path TEXT NOT NULL,
                    session_ids TEXT,
                    metadata TEXT
                )
            """)
            conn.commit()
        
        # Check if there's a default entry
        cursor.execute("SELECT COUNT(*) FROM main_game_data WHERE user_id = 'default'")
        if cursor.fetchone()[0] == 0:
            # Create default entry
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO main_game_data 
                (user_id, created_at, last_updated, default_settings_path, agent_settings_path, session_ids, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('default', now, now, default_settings_path, agent_settings_path, '[]', '{}'))
            conn.commit()
            print(f"Created default main_game_data entry")
