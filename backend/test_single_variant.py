#!/usr/bin/env python3
"""
Test runner for a single experiment variant to verify context length configuration
"""

import json
import sys
import os
import time

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(__file__))

def test_single_variant():
    """Test context length configuration with a single variant"""
    
    print("=== Testing Context Length Configuration ===")
    
    # Load experimental config
    with open('experimental_config.json', 'r') as f:
        config = json.load(f)
    
    # Get the first variant from the first experiment for testing
    exp_name = list(config['experiments'].keys())[0]
    experiment = config['experiments'][exp_name]
    variant = experiment['variants'][0]
    
    print(f"Testing experiment: {experiment['name']}")
    print(f"Testing variant: {variant['name']}")
    
    # Extract configuration
    variant_config = variant['config']
    max_context_length = variant_config.get('max_context_length', 'NOT SET')
    llm_model = variant_config.get('llm_model', 'unknown')
    
    print(f"Model: {llm_model}")
    print(f"Configured context length: {max_context_length}")
    
    # Test memory agent with this configuration
    try:
        from agents.memory_agent import MemoryAgent
        
        # Create memory agent with the configured context length
        mem_agent = MemoryAgent(
            db_path="test_single_variant.db",
            max_context_length=max_context_length if max_context_length != 'NOT SET' else None
        )
        
        print(f"Memory agent context length: {mem_agent.max_context_length}")
        
        # Create a test session
        session = mem_agent.create_session(
            session_id=f"test_{int(time.time())}",
            game_settings={"character_list": [
                {"name": "Alice", "type": "npc"},
                {"name": "Bob", "type": "npc"}
            ]}
        )
        
        print(f"Created test session: {session.session_id}")
        
        # Test adding content that would trigger summarization
        dialogue = mem_agent.start_dialogue("Alice", "Bob", "tavern")
        
        # Add messages until we approach the context limit
        message_count = 0
        test_message = "This is a test message that should accumulate in memory. " * 10
        
        while True:
            mem_agent.add_message(
                dialogue_id=dialogue.dialogue_id,
                sender="Alice" if message_count % 2 == 0 else "Bob",
                receiver="Bob" if message_count % 2 == 0 else "Alice",
                message_text=f"Message {message_count}: {test_message}"
            )
            message_count += 1
            
            # Check Alice's memory length
            alice_memory = mem_agent.get_npc_memory("Alice")
            if alice_memory:
                current_length = alice_memory.messages_summary_length
                print(f"Message {message_count}: Memory length = {current_length}/{max_context_length}")
                
                # Stop when we approach the limit
                if isinstance(max_context_length, int) and current_length > (max_context_length * 0.8):
                    break
            
            # Safety limit
            if message_count > 50:
                break
        
        print(f"Added {message_count} messages before approaching context limit")
        
        # Clean up
        mem_agent.end_dialogue(dialogue.dialogue_id)
        
        try:
            os.remove("test_single_variant.db")
        except FileNotFoundError:
            pass
        
        print("✅ Single variant context length test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_variant()
