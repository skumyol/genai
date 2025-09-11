#!/usr/bin/env python3
"""
Database Manager Script for maingamedata.db

This script provides utilities to:
1. List all entries in the database tables
2. Clean (delete all data) from the database
3. Show database statistics

Usage:
    python db_manager_script.py list                    # List all entries
    python db_manager_script.py list --table sessions   # List specific table
    python db_manager_script.py clean                   # Clean all data (with confirmation)
    python db_manager_script.py clean --force           # Clean without confirmation
    python db_manager_script.py stats                   # Show database statistics
    python db_manager_script.py schema                  # Show table schema
"""

import os
import sys
import sqlite3
import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class DatabaseManagerScript:
    """Database management script for maingamedata.db"""
    
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_path = os.path.join(os.path.dirname(__file__), 'maingamedata.db')
        self.db_path = db_path
        
        if not os.path.exists(self.db_path):
            print(f"Error: Database file not found at {self.db_path}")
            sys.exit(1)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
    
    def list_entries(self, table_name: Optional[str] = None, limit: Optional[int] = None):
        """List entries from database tables"""
        tables = [table_name] if table_name else self.get_all_tables()
        
        for table in tables:
            print(f"\n{'='*60}")
            print(f"TABLE: {table}")
            print(f"{'='*60}")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                if row_count == 0:
                    print("No entries found.")
                    continue
                
                # Get column names
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                # Get data with optional limit
                limit_clause = f" LIMIT {limit}" if limit else ""
                cursor.execute(f"SELECT * FROM {table}{limit_clause}")
                rows = cursor.fetchall()
                
                print(f"Total rows: {row_count}")
                if limit and row_count > limit:
                    print(f"Showing first {limit} rows:")
                print()
                
                # Print column headers
                print(" | ".join(f"{col:<15}" for col in columns))
                print("-" * (len(columns) * 17))
                
                # Print data rows
                for row in rows:
                    values = []
                    for value in row:
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, str) and len(value) > 15:
                            values.append(value[:12] + "...")
                        else:
                            values.append(str(value))
                    print(" | ".join(f"{val:<15}" for val in values))
                
                print()
    
    def show_stats(self):
        """Show database statistics"""
        print(f"\n{'='*60}")
        print("DATABASE STATISTICS")
        print(f"{'='*60}")
        print(f"Database path: {self.db_path}")
        print(f"Database size: {os.path.getsize(self.db_path) / 1024:.2f} KB")
        print()
        
        tables = self.get_all_tables()
        total_rows = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            print(f"{'Table':<25} {'Rows':<10} {'Columns':<10}")
            print("-" * 45)
            
            for table in tables:
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                total_rows += row_count
                
                # Get column count
                cursor.execute(f"PRAGMA table_info({table})")
                col_count = len(cursor.fetchall())
                
                print(f"{table:<25} {row_count:<10} {col_count:<10}")
        
        print("-" * 45)
        print(f"{'TOTAL':<25} {total_rows:<10}")
        print()
    
    def show_schema(self, table_name: Optional[str] = None):
        """Show table schema information"""
        tables = [table_name] if table_name else self.get_all_tables()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for table in tables:
                print(f"\n{'='*60}")
                print(f"SCHEMA: {table}")
                print(f"{'='*60}")
                
                # Get table info
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                print(f"{'Column':<20} {'Type':<15} {'NotNull':<8} {'Default':<15} {'PK':<3}")
                print("-" * 65)
                
                for col in columns:
                    name, col_type, not_null, default_val, pk = col[1:6]
                    default_str = str(default_val) if default_val is not None else ""
                    print(f"{name:<20} {col_type:<15} {bool(not_null):<8} {default_str:<15} {bool(pk):<3}")
                
                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table})")
                fks = cursor.fetchall()
                
                if fks:
                    print("\nForeign Keys:")
                    for fk in fks:
                        print(f"  {fk[3]} -> {fk[2]}.{fk[4]}")
                
                # Get indexes
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = cursor.fetchall()
                
                if indexes:
                    print("\nIndexes:")
                    for idx in indexes:
                        print(f"  {idx[1]} (unique: {bool(idx[2])})")
                
                print()
    
    def clean_database(self, force: bool = False):
        """Clean all data from the database"""
        if not force:
            print("WARNING: This will delete ALL data from the database!")
            print(f"Database path: {self.db_path}")
            response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
            if response not in ['yes', 'y']:
                print("Operation cancelled.")
                return
        
        tables = self.get_all_tables()
        
        # Filter out system tables
        data_tables = [t for t in tables if not t.startswith('sqlite_')]
        
        print(f"\nCleaning {len(data_tables)} tables...")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Disable foreign key constraints temporarily
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            try:
                for table in data_tables:
                    cursor.execute(f"DELETE FROM {table}")
                    print(f"  Cleared table: {table}")
                
                # Reset auto-increment counters
                cursor.execute("DELETE FROM sqlite_sequence")
                
                conn.commit()
                print(f"\nDatabase cleaned successfully!")
                print(f"All data removed from {len(data_tables)} tables.")
                
            except Exception as e:
                conn.rollback()
                print(f"Error cleaning database: {e}")
                sys.exit(1)
            finally:
                # Re-enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")
    
    def vacuum_database(self):
        """Vacuum the database to reclaim space"""
        print("Vacuuming database...")
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        print("Database vacuumed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Database Manager Script for maingamedata.db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python db_manager_script.py list
  python db_manager_script.py list --table sessions --limit 10
  python db_manager_script.py clean
  python db_manager_script.py clean --force
  python db_manager_script.py stats
  python db_manager_script.py schema
  python db_manager_script.py schema --table messages
        """
    )
    
    parser.add_argument('command', choices=['list', 'clean', 'stats', 'schema', 'vacuum'],
                       help='Command to execute')
    parser.add_argument('--table', '-t', help='Specific table name (for list/schema commands)')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of rows to display (for list command)')
    parser.add_argument('--force', '-f', action='store_true', 
                       help='Force operation without confirmation (for clean command)')
    parser.add_argument('--db-path', help='Path to database file (default: ./maingamedata.db)')
    
    args = parser.parse_args()
    
    # Create database manager instance
    db_manager = DatabaseManagerScript(args.db_path)
    
    # Execute command
    if args.command == 'list':
        db_manager.list_entries(args.table, args.limit)
    elif args.command == 'clean':
        db_manager.clean_database(args.force)
    elif args.command == 'stats':
        db_manager.show_stats()
    elif args.command == 'schema':
        db_manager.show_schema(args.table)
    elif args.command == 'vacuum':
        db_manager.vacuum_database()


if __name__ == "__main__":
    main()
