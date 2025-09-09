#!/usr/bin/env python3
"""
Simple wrapper that modifies the experiment config to support continuing from checkpoints.
Uses the original runner.py with modified session handling.
"""

import os
import sys
import json
import sqlite3
import argparse
import subprocess
import tempfile
from typing import Dict, Any, Optional

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(__file__))

def find_checkpoint_session(checkpoint_db: str, experiment_name: str, target_day: int) -> Optional[str]:
    """Find a session that has a checkpoint at the target day"""
    if not os.path.exists(checkpoint_db):
        return None
    
    try:
        conn = sqlite3.connect(checkpoint_db)
        cursor = conn.cursor()
        
        # Find sessions for this experiment that have the target day
        cursor.execute("""
            SELECT DISTINCT s.session_id
            FROM sessions s
            JOIN days d ON s.session_id = d.session_id
            WHERE s.session_id LIKE ? AND d.day = ?
            ORDER BY s.session_id
            LIMIT 1
        """, (f"{experiment_name}%", target_day))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
        
    except Exception as e:
        print(f"Error querying checkpoint database: {e}")
        return None

def modify_config_for_continue(config_path: str, experiment_name: str, 
                             continue_from_day: int, continue_from_session: Optional[str] = None) -> str:
    """
    Modify the experiment config to support continuing from a checkpoint.
    Returns path to the modified config file.
    """
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Find the checkpoint session if not specified
    if not continue_from_session:
        checkpoint_db = os.path.join(os.path.dirname(config_path), 'databases', 'checkpoints.db')
        continue_from_session = find_checkpoint_session(checkpoint_db, experiment_name, continue_from_day)
        if not continue_from_session:
            raise ValueError(f"No checkpoint found for experiment {experiment_name} at day {continue_from_day}")
    
    # Modify the experiment config
    if experiment_name in config["experiments"]:
        experiment = config["experiments"][experiment_name]
        
        # Filter variants to only include the one we're continuing
        original_variants = experiment.get("variants", [])
        continue_variant = None
        
        for variant in original_variants:
            if variant["config"].get("session_id") == continue_from_session:
                continue_variant = variant
                break
        
        if not continue_variant:
            raise ValueError(f"Session {continue_from_session} not found in experiment {experiment_name}")
        
        # Update the experiment to only run the continue variant
        experiment["variants"] = [continue_variant]
        
        # Mark this as a continue operation in session config
        if "session_config" not in config:
            config["session_config"] = {}
        
        config["session_config"]["continue_from_day"] = continue_from_day
        config["session_config"]["continue_from_session"] = continue_from_session
        
        # Adjust duration to account for already completed days
        original_duration = config["session_config"].get("duration_days", 2)
        remaining_days = max(1, original_duration - continue_from_day + 1)
        config["session_config"]["duration_days"] = remaining_days
        
        print(f"Continuing from session {continue_from_session} at day {continue_from_day}")
        print(f"Running {remaining_days} more days (original duration: {original_duration})")
    
    # Write modified config to temporary file
    fd, temp_config_path = tempfile.mkstemp(suffix='.json', prefix='continue_config_')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(config, f, indent=2)
    except:
        os.close(fd)
        raise
    
    return temp_config_path

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Runner with checkpoint continue support")
    parser.add_argument("--config", required=True, help="Path to experiment config file")
    parser.add_argument("--experiment", required=True, help="Experiment name to run")
    parser.add_argument("--continue-from-day", type=int, help="Continue from specified day")
    parser.add_argument("--continue-from-session", help="Specific session ID to continue from")
    
    args = parser.parse_args()
    
    try:
        if args.continue_from_day:
            # Create modified config for continue operation
            temp_config = modify_config_for_continue(
                args.config, 
                args.experiment, 
                args.continue_from_day, 
                args.continue_from_session
            )
            
            # Set environment variable to signal continue mode to the original runner
            env = os.environ.copy()
            env["EXPERIMENTAL_CONTINUE_MODE"] = "1"
            env["EXPERIMENTAL_CONTINUE_DAY"] = str(args.continue_from_day)
            if args.continue_from_session:
                env["EXPERIMENTAL_CONTINUE_SESSION"] = args.continue_from_session
            
            try:
                # Call the original runner with the modified config
                result = subprocess.run([
                    sys.executable, 
                    os.path.join(os.path.dirname(__file__), "runner.py"),
                    "--config", temp_config,
                    "--experiment", args.experiment
                ], env=env, check=True)
                
                print("Continue operation completed successfully")
                
            finally:
                # Clean up temporary config
                try:
                    os.unlink(temp_config)
                except:
                    pass
        else:
            # Normal operation - just call the original runner
            result = subprocess.run([
                sys.executable,
                os.path.join(os.path.dirname(__file__), "runner.py"),
                "--config", args.config,
                "--experiment", args.experiment
            ], check=True)
            
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
