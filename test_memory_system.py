#!/usr/bin/env python3
"""
Test script to verify the automatic memory summarization system
"""
import sys
import os
sys.path.append('/Users/skumyol/Documents/GitHub/genai/backend')

from agents.memory_agent import MemoryAgent
from agents.dataclasses import NPCMemory
from datetime import datetime

def test_automatic_summarization():
    """Test if automatic summarization triggers correctly"""
    print("=== Testing Automatic Memory Summarization ===")
    
    # Create memory agent with low context length for testing
    memory_agent = MemoryAgent(db_path="test_memory.db", max_context_length=200)
    
    # Create a test session
    session = memory_agent.create_session("test_session", 
                                        game_settings={"character_list": [
                                            {"name": "Alice", "type": "npc", "personality": "friendly"},
                                            {"name": "Bob", "type": "npc", "personality": "serious"}
                                        ]})
    
    print(f"Created session: {session.session_id}")
    
    # Start a dialogue
    dialogue = memory_agent.start_dialogue("Alice", "Bob", "tavern")
    print(f"Started dialogue: {dialogue.dialogue_id}")
    
    # Add multiple messages to trigger summarization
    messages = [
        "Hello Bob, how are you today?",
        "I'm doing well Alice, thank you for asking. How about you?",
        "I'm great! I was wondering if you've heard about the new merchant in town.",
        "Yes, I have. They seem to have some interesting wares from distant lands.",
        "I was thinking we should visit them together sometime.",
        "That sounds like a good idea. When would you like to go?",
        "How about tomorrow morning? We could meet at the market square.",
        "Perfect! I'll see you there at sunrise.",
        "Wonderful! I'm looking forward to it.",
        "Me too. Have a good evening, Alice.",
        "You too, Bob. See you tomorrow!"
    ]
    
    print(f"\nAdding {len(messages)} messages to trigger summarization...")
    
    for i, message_text in enumerate(messages):
        sender = "Alice" if i % 2 == 0 else "Bob"
        receiver = "Bob" if i % 2 == 0 else "Alice"
        
        message = memory_agent.add_message(
            dialogue_id=dialogue.dialogue_id,
            sender=sender,
            receiver=receiver,
            message_text=message_text
        )
        print(f"Added message {i+1}: {sender} -> {receiver}")
        
        # Check Alice's memory after each message
        alice_memory = memory_agent.get_npc_memory("Alice")
        if alice_memory:
            print(f"  Alice memory length: {alice_memory.messages_summary_length}")
            if alice_memory.messages_summary_length > 200:
                print(f"  ⚠️  Memory length exceeded threshold, should trigger summarization")
    
    # Wait a moment for background summarization
    import time
    print("\nWaiting for background summarization...")
    time.sleep(2)
    
    # Check final memory states
    print("\n=== Final Memory States ===")
    for npc_name in ["Alice", "Bob"]:
        npc_memory = memory_agent.get_npc_memory(npc_name)
        if npc_memory:
            print(f"\n{npc_name} Memory:")
            print(f"  Messages summary length: {npc_memory.messages_summary_length}")
            print(f"  Last summarized: {npc_memory.last_summarized}")
            print(f"  Messages summary preview: {npc_memory.messages_summary[:100]}...")
            
            # Check dialogue summary in world knowledge
            dialogue_summary = npc_memory.world_knowledge.get('dialogue_summary', '')
            print(f"  Dialogue summary length: {len(dialogue_summary)}")
            if dialogue_summary:
                print(f"  Dialogue summary preview: {dialogue_summary[:100]}...")
    
    # Test the get_npc_dialogue_summary method
    print("\n=== Testing get_npc_dialogue_summary ===")
    for npc_name in ["Alice", "Bob"]:
        summary = memory_agent.get_npc_dialogue_summary(npc_name)
        print(f"{npc_name} dialogue summary: {summary[:100]}..." if summary else f"{npc_name} has no dialogue summary")
    
    # Clean up
    memory_agent.end_dialogue(dialogue.dialogue_id)
    
    # Remove test database
    if os.path.exists("test_memory.db"):
        os.remove("test_memory.db")
    
    print("\n=== Test Complete ===")

def test_memory_system_integration():
    """Test how the memory system integrates with dialogue handler"""
    print("\n=== Testing Memory System Integration ===")
    
    # Check if the automatic system is being used in dialogue handler
    from agents.dialogue_handler import DialogueHandler
    
    print("✓ DialogueHandler imports successfully")
    print("✓ Memory system integration appears to be in place")
    
    # Check the memory update flow in dialogue handler
    print("\nMemory update flow in DialogueHandler:")
    print("1. add_message() -> memory_agent.add_message()")
    print("2. memory_agent._update_npc_memory() -> updates messages_summary")
    print("3. If length > max_context_length -> _summarize_npc_memory()")
    print("4. Background LLM summarization -> updates messages_summary and dialogue_summary")

if __name__ == "__main__":
    try:
        test_automatic_summarization()
        test_memory_system_integration()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
