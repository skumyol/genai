import asyncio
import logging
from threading import Event
import os

from agents.memory_agent import MemoryAgent
from game_loop_manager import GameLoopManager

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/game_loop.log"),
        logging.StreamHandler()
    ]
)

llm_models = ["mistralai/ministral-8b"]

async def main():
    """Initializes and runs the game loop for a few cycles."""
    logger = logging.getLogger(__name__)
    logger.info("Initializing game loop for a standalone test run...")

    # Initialize MemoryAgent with the schema-compatible DB and create a new session
    memory_agent = MemoryAgent(db_path="game_memory.db")
    session_info = memory_agent.create_session()
    logger.info(f"Started a new session: {session_info.session_id}")

    # Initialize GameLoopManager
    # We don't have an SSE manager or a stop event in this context
    game_loop_manager = GameLoopManager(
        memory_agent=memory_agent,
        sse_manager=None, # No SSE for standalone mode
        stop_event=Event(), # A dummy event
        llm_provider="openrouter", # or your preferred provider
        llm_model=llm_models[0] # or your preferred model
    )

    logger.info("Starting the game loop...")

    # Restrict phases to morning and noon for faster run
    game_loop_manager.phases = ["MORNING", "NOON"]

    # Run for three days
    num_days_to_run = 1
    for day in range(1, num_days_to_run + 1):
        logger.info(f"--- Starting Day {day} ---")
        await game_loop_manager.run_day_cycle()
        if game_loop_manager._should_stop():
            logger.info("Stop event detected. Ending simulation.")
            break
        logger.info(f"--- Completed Day {day} ---")

    logger.info("Standalone game loop test run finished.")

if __name__ == "__main__":
    asyncio.run(main())
