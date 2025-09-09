"""Test script to isolate logging configuration"""
import os
from utils.logger_util import setup_rotating_logger
from agents.flow_agents.schedule_agent import ScheduleAgent

def test_schedule_agent_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    
    # Ensure logs directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Test direct logger
    direct_logger = setup_rotating_logger("direct_test", os.path.join(log_dir, "direct_test.log"))
    direct_logger.info("This is a direct test log message")
    
    # Test ScheduleAgent logger
    agent = ScheduleAgent()
    if hasattr(agent, 'logger'):
        agent.logger.info("ScheduleAgent test log message")
    else:
        print("ScheduleAgent has no logger attribute")

if __name__ == "__main__":
    test_schedule_agent_logging()
    print(f"Test complete. Check {os.path.join(os.path.dirname(__file__), 'logs')} for logs")
