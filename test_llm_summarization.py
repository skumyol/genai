#!/usr/bin/env python3
"""
Test script to debug LLM summarization issues
"""
import sys
import os
sys.path.append('/Users/skumyol/Documents/GitHub/genai/backend')

def test_llm_call():
    """Test if LLM call works"""
    print("=== Testing LLM Call ===")
    
    try:
        from llm_client import call_llm
        
        # Test basic LLM call
        provider = os.environ.get("MEMORY_SUMMARY_PROVIDER", "openrouter")
        model = os.environ.get("MEMORY_SUMMARY_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
        
        print(f"Testing LLM: {provider}/{model}")
        
        response = call_llm(
            provider=provider,
            model=model,
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, this is a test!'",
            temperature=0.2
        )
        
        print(f"✓ LLM Response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ LLM Call Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_memory_summarization_debug():
    """Test memory summarization with debug output"""
    print("\n=== Testing Memory Summarization with Debug ===")
    
    from agents.memory_agent import MemoryAgent
    import time
    import threading
    
    # Create memory agent
    memory_agent = MemoryAgent(db_path="debug_memory.db", max_context_length=100)
    
    # Create session
    session = memory_agent.create_session("debug_session", 
                                        game_settings={"character_list": [
                                            {"name": "Alice", "type": "npc", "personality": "friendly"}
                                        ]})
    
    # Start dialogue
    dialogue = memory_agent.start_dialogue("Alice", "Bob", "tavern")
    
    # Add messages to exceed threshold
    long_message = "This is a very long message that should definitely exceed the context length threshold when combined with other messages. " * 5
    
    for i in range(3):
        memory_agent.add_message(
            dialogue_id=dialogue.dialogue_id,
            sender="Alice",
            receiver="Bob", 
            message_text=f"Message {i+1}: {long_message}"
        )
        
        alice_memory = memory_agent.get_npc_memory("Alice")
        print(f"After message {i+1}: length = {alice_memory.messages_summary_length}")
    
    # Check if summarization was triggered
    alice_memory = memory_agent.get_npc_memory("Alice")
    if alice_memory.messages_summary_length > 100:
        print(f"✓ Summarization should be triggered (length: {alice_memory.messages_summary_length})")
        
        # Check if NPC is in summarizing set
        if hasattr(memory_agent, '_summarizing_npcs'):
            if "Alice" in memory_agent._summarizing_npcs:
                print("✓ Alice is in _summarizing_npcs set")
            else:
                print("❌ Alice is NOT in _summarizing_npcs set")
        
        # Wait for background thread
        print("Waiting 5 seconds for background summarization...")
        time.sleep(5)
        
        # Check results
        alice_memory = memory_agent.get_npc_memory("Alice")
        print(f"After wait: length = {alice_memory.messages_summary_length}")
        print(f"Last summarized: {alice_memory.last_summarized}")
        
        if alice_memory.last_summarized:
            print("✓ Summarization completed successfully")
        else:
            print("❌ Summarization did not complete")
    
    # Clean up
    memory_agent.end_dialogue(dialogue.dialogue_id)
    if os.path.exists("debug_memory.db"):
        os.remove("debug_memory.db")

if __name__ == "__main__":
    # Test LLM first
    if test_llm_call():
        test_memory_summarization_debug()
    else:
        print("Skipping memory test due to LLM failure")
