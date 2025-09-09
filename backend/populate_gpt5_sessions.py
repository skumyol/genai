#!/usr/bin/env python3
"""
Script to populate GPT-5 experiment sessions with dialogues and messages
"""

import json
import sqlite3
from datetime import datetime
import re
from collections import defaultdict

def extract_day_and_time_from_dialogue_id(dialogue_id):
    """Extract day and time period from dialogue_id like 'dialogue_1_MORNING'"""
    match = re.match(r'dialogue_(\d+)_(\w+)', dialogue_id)
    if match:
        return int(match.group(1)), match.group(2).lower()
    return None, None

def create_dialogue_id_mapping(messages, conn):
    """Create mapping from JSON dialogue IDs to sequential numeric IDs continuing from database"""
    cursor = conn.cursor()
    
    # Get current dialogue counter
    cursor.execute("SELECT next_id FROM id_counters WHERE entity = 'dialogues'")
    result = cursor.fetchone()
    next_dialogue_id = result[0] if result else 0
    
    # Get unique dialogue IDs and sort them
    unique_dialogue_ids = set(msg['dialogue_id'] for msg in messages)
    
    def sort_key(dialogue_id):
        day, time_period = extract_day_and_time_from_dialogue_id(dialogue_id)
        if day is None or time_period is None:
            return (999, 999)  # Put invalid IDs at the end
        time_order = ['morning', 'noon', 'afternoon', 'evening', 'night']
        try:
            time_index = time_order.index(time_period)
        except ValueError:
            time_index = 999
        return (day, time_index)
    
    sorted_dialogue_ids = sorted(unique_dialogue_ids, key=sort_key)
    
    # Create mapping to sequential numeric IDs starting from next_dialogue_id
    mapping = {}
    for i, dialogue_id in enumerate(sorted_dialogue_ids):
        mapping[dialogue_id] = str(next_dialogue_id + i)
    
    # Update counter for future use
    new_next_id = next_dialogue_id + len(sorted_dialogue_ids)
    cursor.execute("UPDATE id_counters SET next_id = ? WHERE entity = 'dialogues'", (new_next_id,))
    
    return mapping

def create_message_id_mapping(messages, conn):
    """Create mapping from array position to sequential numeric IDs continuing from database"""
    cursor = conn.cursor()
    
    # Get current message counter
    cursor.execute("SELECT next_id FROM id_counters WHERE entity = 'messages'")
    result = cursor.fetchone()
    next_message_id = result[0] if result else 0
    
    # Create mapping based on array position since message IDs have duplicates
    message_mapping = {}
    for i, msg in enumerate(messages):
        message_mapping[i] = str(next_message_id + i)
    
    # Update counter for future use
    new_next_id = next_message_id + len(messages)
    cursor.execute("UPDATE id_counters SET next_id = ? WHERE entity = 'messages'", (new_next_id,))
    
    return message_mapping

def populate_session_data(session_id, messages_file_path, db_path):
    """Populate session with dialogues and messages from JSON file"""
    
    # Load messages data
    with open(messages_file_path, 'r') as f:
        data = json.load(f)
    
    messages = data['messages']
    print(f"Loading {len(messages)} messages for session {session_id}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create ID mappings to match existing database schema - must be done after DB connection
        dialogue_mapping = create_dialogue_id_mapping(messages, conn)
        message_mapping = create_message_id_mapping(messages, conn)
        
        print(f"Created mappings for {len(dialogue_mapping)} dialogues and {len(message_mapping)} messages")
        
        # Group messages by their NEW dialogue_id
        dialogues_data = defaultdict(list)
        for i, msg in enumerate(messages):
            new_dialogue_id = dialogue_mapping[msg['dialogue_id']]
            new_message_id = message_mapping[i]  # Use array index
            
            # Create updated message with new IDs
            updated_msg = msg.copy()
            updated_msg['dialogue_id'] = new_dialogue_id
            updated_msg['message_id'] = new_message_id
            
            dialogues_data[new_dialogue_id].append(updated_msg)
        
        print(f"Grouped messages into {len(dialogues_data)} dialogues")
        
        # Clear existing data for this session (if any)
        cursor.execute("DELETE FROM messages WHERE dialogue_id IN (SELECT dialogue_id FROM dialogues WHERE session_id = ?)", (session_id,))
        cursor.execute("DELETE FROM dialogues WHERE session_id = ?", (session_id,))
        print(f"Cleared existing data for session {session_id}")
        
        # Process each dialogue
        for dialogue_id, msgs in dialogues_data.items():
            # Get original dialogue info for day/time extraction
            original_dialogue_id = None
            for orig_id, new_id in dialogue_mapping.items():
                if new_id == dialogue_id:
                    original_dialogue_id = orig_id
                    break
            
            day, time_period = extract_day_and_time_from_dialogue_id(original_dialogue_id)
            if day is None or time_period is None:
                print(f"Warning: Could not parse dialogue_id {original_dialogue_id}")
                continue
            
            # Sort messages by their numeric ID to maintain order
            msgs.sort(key=lambda x: int(x['message_id']))
            
            # Get dialogue info from first message
            first_msg = msgs[0]
            initiator = first_msg['sender']
            receiver = first_msg['receiver']
            started_at = first_msg['timestamp']
            ended_at = msgs[-1]['timestamp']  # Use last message timestamp
            
            # Create message_ids list
            message_ids = [msg['message_id'] for msg in msgs]
            message_ids_json = json.dumps(message_ids)
            
            # Calculate total text length
            total_text_length = sum(len(msg['message_text']) for msg in msgs)
            
            # Insert dialogue
            cursor.execute("""
                INSERT INTO dialogues (
                    dialogue_id, session_id, initiator, receiver, day, 
                    location, time_period, started_at, ended_at, 
                    message_ids, total_text_length
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dialogue_id, session_id, initiator, receiver, day,
                "Crystal Spire",  # Default location
                time_period, started_at, ended_at,
                message_ids_json, total_text_length
            ))
            
            # Insert messages
            for msg in msgs:
                cursor.execute("""
                    INSERT INTO messages (
                        message_id, dialogue_id, sender, receiver, 
                        message_text, timestamp, sender_opinion, receiver_opinion
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg['message_id'], msg['dialogue_id'],
                    msg['sender'], msg['receiver'],
                    msg['message_text'], msg['timestamp'],
                    msg['sender_opinion'], msg['receiver_opinion']
                ))
            
            print(f"Inserted dialogue {dialogue_id} (orig: {original_dialogue_id}) with {len(msgs)} messages")
        
        # Update session with dialogue_ids (using new numeric IDs)
        all_dialogue_ids = list(dialogues_data.keys())
        all_dialogue_ids.sort(key=int)  # Sort numerically
        dialogue_ids_json = json.dumps(all_dialogue_ids)
        
        cursor.execute("""
            UPDATE sessions 
            SET dialogue_ids = ?, last_updated = ?
            WHERE session_id = ?
        """, (dialogue_ids_json, datetime.now().isoformat(), session_id))
        
        # Update or create NPC memories
        npcs = set()
        for msgs in dialogues_data.values():
            for msg in msgs:
                npcs.add(msg['sender'])
                npcs.add(msg['receiver'])
        
        print(f"Found NPCs: {npcs}")
        
        for npc in npcs:
            # Get dialogues this NPC participated in (using new numeric IDs)
            npc_dialogue_ids = []
            for dialogue_id, msgs in dialogues_data.items():
                if any(msg['sender'] == npc or msg['receiver'] == npc for msg in msgs):
                    npc_dialogue_ids.append(dialogue_id)
            
            npc_dialogue_ids.sort(key=int)  # Sort numerically
            npc_dialogue_ids_json = json.dumps(npc_dialogue_ids)
            
            # Create or update NPC memory
            cursor.execute("""
                INSERT OR REPLACE INTO npc_memories (
                    npc_name, session_id, dialogue_ids, 
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                npc, session_id, npc_dialogue_ids_json,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            print(f"Updated memory for NPC {npc} with {len(npc_dialogue_ids)} dialogues")
        
        # Create day entries
        days_data = defaultdict(lambda: defaultdict(list))
        for dialogue_id in dialogues_data.keys():
            # Find original dialogue ID to extract day/time
            original_dialogue_id = None
            for orig_id, new_id in dialogue_mapping.items():
                if new_id == dialogue_id:
                    original_dialogue_id = orig_id
                    break
            
            day, time_period = extract_day_and_time_from_dialogue_id(original_dialogue_id)
            if day is not None and time_period is not None:
                days_data[day][time_period].append(dialogue_id)
        
        for day in days_data:
            for time_period, dialogue_ids in days_data[day].items():
                dialogue_ids.sort(key=int)  # Sort numerically
                dialogue_ids_json = json.dumps(dialogue_ids)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO days (
                        session_id, day, time_period, started_at,
                        dialogue_ids, active_npcs
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id, day, time_period, datetime.now().isoformat(),
                    dialogue_ids_json, json.dumps(list(npcs))
                ))
        
        print(f"Created day entries for {len(days_data)} days")
        
        # Commit all changes
        conn.commit()
        print(f"Successfully populated session {session_id}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error populating session {session_id}: {e}")
        raise
    finally:
        conn.close()

def main():
    """Main function to populate both GPT-5 sessions"""
    db_path = "databases/checkpoints.db"
    
    # Show current state before starting
    print("=" * 60)
    print("CURRENT DATABASE STATE")
    print("=" * 60)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT next_id FROM id_counters WHERE entity = 'dialogues'")
    next_dialogue_id = cursor.fetchone()[0]
    cursor.execute("SELECT next_id FROM id_counters WHERE entity = 'messages'")
    next_message_id = cursor.fetchone()[0]
    
    print(f"Next dialogue ID will be: {next_dialogue_id}")
    print(f"Next message ID will be: {next_message_id}")
    
    # Count messages in each file
    with open("databases/messages_gpt5_rep_off.json", 'r') as f:
        rep_off_count = len(json.load(f)['messages'])
    with open("databases/messages_gpt5_rep_on.json", 'r') as f:
        rep_on_count = len(json.load(f)['messages'])
    
    print(f"Rep OFF will use dialogue IDs: {next_dialogue_id} to {next_dialogue_id + 49}")
    print(f"Rep OFF will use message IDs: {next_message_id} to {next_message_id + rep_off_count - 1}")
    print(f"Rep ON will use dialogue IDs: {next_dialogue_id + 50} to {next_dialogue_id + 99}")
    print(f"Rep ON will use message IDs: {next_message_id + rep_off_count} to {next_message_id + rep_off_count + rep_on_count - 1}")
    
    conn.close()
    
    print(f"\nBackup created: databases/checkpoints_backup_[timestamp].db")
    
    input("Press Enter to continue with population or Ctrl+C to cancel...")
    
    # Populate rep_off session
    print("\n" + "=" * 50)
    print("Populating exp_gpt5_all_gpt5_rep_off session")
    print("=" * 50)
    populate_session_data(
        "exp_gpt5_all_gpt5_rep_off",
        "databases/messages_gpt5_rep_off.json",
        db_path
    )
    
    # Populate rep_on session
    print("\n" + "=" * 50)
    print("Populating exp_gpt5_all_gpt5_rep_on session")
    print("=" * 50)
    populate_session_data(
        "exp_gpt5_all_gpt5_rep_on",
        "databases/messages_gpt5_rep_on.json",
        db_path
    )
    
    print("\n" + "=" * 50)
    print("Population complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()
