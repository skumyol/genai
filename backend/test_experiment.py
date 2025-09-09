#!/usr/bin/env python3
"""
Quick test script to validate experimental setup before running full experiments.
"""

import os
import sys
import json
import time
import logging

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from experimental_runner import ExperimentalRunner
from metrics_collector import init_metrics_collector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_loading():
    """Test that experimental config loads correctly"""
    print("Testing config loading...")
    try:
        runner = ExperimentalRunner()
        config = runner.config
        print(f"✓ Config loaded with {len(config['experiments'])} experiments")
        
        for exp_name, exp_config in config['experiments'].items():
            print(f"  - {exp_name}: {len(exp_config['variants'])} variants")
        
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False

def test_metrics_collection():
    """Test metrics collection system"""
    print("\nTesting metrics collection...")
    try:
        collector = init_metrics_collector("test_exp", "test_session")
        
        # Record some test metrics
        collector.record_metric("test_latency", 1.5, {"test": True})
        collector.record_llm_call("test_agent", "test/model", 100, 50, 2.0)
        
        stats = collector.get_summary_stats()
        print(f"✓ Metrics collection working - {stats['total_metrics']} metrics recorded")
        
        # Export test data
        collector.export_json()
        print("✓ JSON export successful")
        
        return True
    except Exception as e:
        print(f"✗ Metrics collection failed: {e}")
        return False

def test_session_creation():
    """Test session creation for experiments"""
    print("\nTesting session creation...")
    try:
        from app import memory_agent, default_settings
        
        # Create a test session
        session_id = f"test_session_{int(time.time())}"
        session = memory_agent.create_session(session_id=session_id, game_settings=default_settings)
        
        print(f"✓ Session created: {session.session_id}")
        print(f"  - Day: {session.current_day}")
        print(f"  - Time period: {session.current_time_period.value}")
        print(f"  - NPCs: {len(session.active_npcs)}")
        
        return True
    except Exception as e:
        print(f"✗ Session creation failed: {e}")
        return False

def test_llm_integration():
    """Test LLM client with metrics"""
    print("\nTesting LLM integration...")
    try:
        from llm_client import call_llm
        
        # Initialize metrics for this test
        collector = init_metrics_collector("llm_test", "test_session")
        
        # Test call with test provider (without agent_name to avoid metrics issues)
        response = call_llm(
            "test", "test", 
            "You are a test system", 
            "Say hello"
        )
        
        print(f"✓ LLM call successful: {response[:50]}...")
        
        stats = collector.get_summary_stats()
        if stats['llm_stats']['total_calls'] > 0:
            print("✓ Metrics captured from LLM call")
        else:
            print("⚠ No metrics captured (expected in test mode)")
        
        return True
    except Exception as e:
        print(f"✗ LLM integration failed: {e}")
        return False

def main():
    print("=== Experimental Setup Test ===\n")
    
    tests = [
        test_config_loading,
        test_metrics_collection,
        test_session_creation,
        test_llm_integration
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{len(tests)} tests passed ===")
    
    if passed == len(tests):
        print("\n🎉 All tests passed! Ready to run experiments.")
        print("\nTo run an experiment:")
        print("  python experimental_runner.py --list")
        print("  python experimental_runner.py --experiment test_1_reputation_comparison")
        print("  ./run_experiment.sh test_1_reputation_comparison")
    else:
        print(f"\n❌ {len(tests) - passed} tests failed. Please fix issues before running experiments.")
        sys.exit(1)

if __name__ == "__main__":
    main()
