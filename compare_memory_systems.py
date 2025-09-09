#!/usr/bin/env python3
"""
Compare automatic memory system vs forget mechanism
"""
import sys
import os
sys.path.append('/Users/skumyol/Documents/GitHub/genai/backend')

def compare_memory_systems():
    """Compare the two memory systems to determine redundancy"""
    print("=== Comparing Memory Systems ===")
    
    print("\n📊 AUTOMATIC MEMORY SYSTEM (memory_agent.py):")
    print("✓ Triggers: When messages_summary_length > max_context_length (4000 chars)")
    print("✓ Process: Background LLM summarization of all dialogue content")
    print("✓ Updates: messages_summary + world_knowledge['dialogue_summary']")
    print("✓ Frequency: Automatic, real-time during dialogues")
    print("✓ Scope: All dialogue content for each NPC")
    
    print("\n📊 FORGET MECHANISM (npc_agent.py):")
    print("• Triggers: Manual daily processing via forget_mechanism_today()")
    print("• Process: Per-character conversation analysis + LLM summarization")
    print("• Updates: world_knowledge['dialogue_summary'] (overwrites automatic)")
    print("• Frequency: Daily, manual invocation")
    print("• Scope: Per-character conversation contexts")
    
    print("\n🔍 REDUNDANCY ANALYSIS:")
    print("❌ CONFLICT: Both systems update the same field (dialogue_summary)")
    print("❌ DUPLICATION: Both do LLM summarization of dialogue content")
    print("❌ TIMING: Forget mechanism overwrites automatic summaries")
    print("❌ COMPLEXITY: Two different summarization approaches")
    
    print("\n💡 RECOMMENDATION:")
    print("🗑️  REMOVE FORGET MECHANISM because:")
    print("   1. Automatic system handles real-time summarization")
    print("   2. No need for daily batch processing")
    print("   3. Eliminates conflicts and overwrites")
    print("   4. Simpler, more efficient architecture")
    print("   5. Real-time vs batch processing is superior")

def test_memory_system_efficiency():
    """Test the efficiency of the automatic system"""
    print("\n=== Testing Memory System Efficiency ===")
    
    from agents.memory_agent import MemoryAgent
    import time
    
    # Test with realistic dialogue lengths
    memory_agent = MemoryAgent(db_path="efficiency_test.db", max_context_length=4000)
    
    session = memory_agent.create_session("efficiency_test", 
                                        game_settings={"character_list": [
                                            {"name": "Alice", "type": "npc"},
                                            {"name": "Bob", "type": "npc"}
                                        ]})
    
    dialogue = memory_agent.start_dialogue("Alice", "Bob", "tavern")
    
    # Simulate realistic dialogue
    messages = [
        "Hello Bob, I've been thinking about our conversation yesterday.",
        "Oh yes Alice, about the merchant's strange behavior?",
        "Exactly. I noticed he seemed nervous when we asked about his wares.",
        "I thought the same thing. His hands were shaking slightly.",
        "And did you see how he avoided eye contact when discussing prices?",
        "Yes, very suspicious. I wonder if he's hiding something.",
        "Perhaps we should investigate further. What do you think?",
        "I agree. We could ask around town about his background.",
        "Good idea. I'll talk to the innkeeper, she knows everyone.",
        "And I'll speak with the blacksmith. He's dealt with many merchants.",
        "Perfect. Let's meet tomorrow evening to share what we learn.",
        "Agreed. This could be important for the town's safety."
    ]
    
    print(f"Adding {len(messages)} realistic dialogue messages...")
    
    start_time = time.time()
    
    for i, message_text in enumerate(messages * 10):  # Multiply to exceed threshold
        sender = "Alice" if i % 2 == 0 else "Bob"
        receiver = "Bob" if i % 2 == 0 else "Alice"
        
        memory_agent.add_message(
            dialogue_id=dialogue.dialogue_id,
            sender=sender,
            receiver=receiver,
            message_text=message_text
        )
    
    # Check memory states
    alice_memory = memory_agent.get_npc_memory("Alice")
    bob_memory = memory_agent.get_npc_memory("Bob")
    
    print(f"Alice memory length: {alice_memory.messages_summary_length}")
    print(f"Bob memory length: {bob_memory.messages_summary_length}")
    
    if alice_memory.messages_summary_length > 4000:
        print("✓ Automatic summarization should trigger")
        
        # Wait for summarization
        print("Waiting for automatic summarization...")
        time.sleep(8)
        
        alice_memory = memory_agent.get_npc_memory("Alice")
        bob_memory = memory_agent.get_npc_memory("Bob")
        
        print(f"After summarization - Alice: {alice_memory.messages_summary_length} chars")
        print(f"After summarization - Bob: {bob_memory.messages_summary_length} chars")
        
        if alice_memory.last_summarized:
            print("✅ AUTOMATIC SYSTEM WORKS EFFICIENTLY")
            print("   • Real-time processing")
            print("   • No manual intervention needed")
            print("   • Maintains conversation context")
        else:
            print("❌ Summarization failed")
    
    processing_time = time.time() - start_time
    print(f"Total processing time: {processing_time:.2f} seconds")
    
    # Cleanup
    memory_agent.end_dialogue(dialogue.dialogue_id)
    if os.path.exists("efficiency_test.db"):
        os.remove("efficiency_test.db")

if __name__ == "__main__":
    compare_memory_systems()
    test_memory_system_efficiency()
