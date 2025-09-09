#!/usr/bin/env python3
"""
Experimental headless game runner for testing different LLM configurations.
Runs 2-day game sessions with comprehensive metrics collection.
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from datetime import datetime
from typing import Dict, Any, Optional

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from agents.memory_agent import MemoryAgent
from metrics_collector import init_metrics_collector, get_metrics_collector
from game_loop_manager import GameLoopManager
from sse_manager import SSEManager

# We configure logging inside entrypoints so imports don't truncate logs unexpectedly
logger = logging.getLogger(__name__)

def _setup_experiment_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Allow caller to override the log file per process to avoid collisions
            logging.FileHandler(os.environ.get('EXP_RUN_LOG', 'experimental_run.log'), mode='a'),
            logging.StreamHandler()
        ],
        force=True,
    )
logger = logging.getLogger(__name__)

def _load_default_settings(path: Optional[str] = None) -> Dict[str, Any]:
    try:
        base = os.path.dirname(__file__)
        cfg_path = path or os.path.join(base, 'default_settings.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_checkpoint_db_path() -> str:
    base = os.path.dirname(__file__)
    # Prefer game_settings.json if present
    try:
        gs_path = os.path.join(base, 'game_settings.json')
        with open(gs_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        p = (((cfg.get('databases') or {}) if isinstance(cfg, dict) else {}).get('checkpoints'))
        if p:
            return p if os.path.isabs(p) else os.path.join(base, p)
    except Exception:
        pass
    # Fallback default
    return os.path.join(base, 'databases', 'checkpoints.db')


class ExperimentalRunner:
    def __init__(self, config_path: str = "experimental_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.current_experiment = None
        self.current_variant = None
        self.metrics_collector = None
        # Dedicated MemoryAgent bound to checkpoint DB for experiments
        # We'll update the context length per experiment variant
        self.exp_memory_agent = MemoryAgent(db_path=_resolve_checkpoint_db_path())
        self.default_settings = _load_default_settings()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load experimental configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def _apply_llm_config(self, variant_config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply LLM configuration to agents and return game agent config"""
        logger.info("Applying LLM configuration: %s", variant_config.get("name", "Unknown"))
        
        # Runner-local flags
        self._reputation_enabled = bool(variant_config["config"].get("reputation_enabled", True))
        
        # Apply context length configuration to memory agent
        max_context_length = variant_config["config"].get("max_context_length")
        if max_context_length is not None:
            self.exp_memory_agent.max_context_length = int(max_context_length)
            logger.info(f"Set memory agent context length to: {max_context_length}")
        
        # Optionally capture top-level provider/model (unused directly; agents use per-agent configs)
        top_provider = variant_config["config"].get("llm_provider")
        top_model = variant_config["config"].get("llm_model")
        # Save summarizer configuration for this run
        self._summary_provider = top_provider
        self._summary_model = top_model
        
        # Pass context length and summarizer config to memory agent
        self.exp_memory_agent._summary_provider = top_provider
        self.exp_memory_agent._summary_model = top_model

        # Return game agent configuration for GameLoopManager
        game_config = variant_config["config"].get("game_agents", {})
        for agent_name, agent_config in game_config.items():
            logger.info(f"Game agent {agent_name} configured: {agent_config['provider']}/{agent_config['model']}")
        
        return game_config
    
    def _create_session(self, experiment_id: str, variant_id: str, fixed_session_id: Optional[str] = None, resume: bool = False) -> str:
        """Create a new game session for the experiment or resume existing one
        
        Args:
            experiment_id: Experiment name
            variant_id: Variant ID
            fixed_session_id: Optional fixed session ID (from config)
            resume: If True, don't delete existing session data
            
        Returns:
            Session ID
        """
        session_prefix = self.config.get("session_config", {}).get("session_prefix", "exp_")
        # Allow fixed session id from config for deterministic runs; else include timestamp
        if fixed_session_id:
            session_id = fixed_session_id
        else:
            # For resuming, don't append timestamp to ensure we use the same session ID
            session_id = f"{session_prefix}{experiment_id}_{variant_id}"
            if not resume:
                session_id = f"{session_id}_{int(time.time())}"
        
        # If not resuming, purge prior data for this session
        if not resume:
            try:
                logger.info(f"Creating fresh session: {session_id}")
                self.exp_memory_agent.db_manager.delete_session_data(session_id)
            except Exception as e:
                # Safe to proceed even if cleanup fails (tables may be empty)
                logger.warning(f"Failed to clear session data: {e}")
        else:
            logger.info(f"Resuming existing session: {session_id}")
        
        # Create session with default settings (or load existing if resuming)
        try:
            # Try to load first if resuming
            if resume and self.exp_memory_agent.load_session(session_id):
                logger.info(f"Loaded existing session: {session_id}")
                return session_id
        except Exception as e:
            logger.warning(f"Could not load existing session: {e}")
        
        # Create new session if loading failed or not resuming
        session = self.exp_memory_agent.create_session(session_id=session_id, game_settings=self.default_settings)
        # Tag session with experiment metadata for later frontend monitoring/analysis
        try:
            gs = session.game_settings or {}
            gs['experiment'] = {
                'type': 'self',
                'experiment_name': experiment_id,
                'variant_id': variant_id,
            }
            session.game_settings = gs
            self.exp_memory_agent.db_manager.update_session(session)
        except Exception:
            pass
        logger.info(f"Created experimental session: {session_id}")
        
        return session_id
    
    def _run_game_session(self, session_id: str, duration_days: int = 2, game_agent_config: Dict[str, Any] = None, reputation_enabled: bool = True) -> Dict[str, Any]:
        """Run a complete game session with metrics collection"""
        logger.info(f"Starting {duration_days}-day game session: {session_id}")
        
        # Initialize metrics collection
        collector = get_metrics_collector()
        if not collector:
            logger.error("Metrics collector not initialized")
            return {"success": False, "error": "No metrics collector"}
        
        # Create SSE manager for game loop (even though we're headless)
        sse_manager = SSEManager(None)  # No socketio for headless mode
        
        # Create stop event for controlled shutdown
        stop_event = threading.Event()
        
        session_start_time = time.time()
        
        # Extract LLM configuration for game agents
        game_agent_config = game_agent_config or {}
        
        # Determine primary LLM provider/model for GameLoopManager defaults.
        # Use the top-level summarizer provider/model from config if available (ensures summaries use GPT-5 by default),
        # otherwise fall back to per-agent dialogue/lifecycle config, then env, then 'test'.
        if getattr(self, "_summary_provider", None) or getattr(self, "_summary_model", None):
            primary_llm_provider = self._summary_provider or os.environ.get("LLM_PROVIDER") or "test"
            primary_llm_model = self._summary_model or os.environ.get("LLM_MODEL") or "test"
        elif "dialogue_agent" in game_agent_config:
            primary_llm_provider = game_agent_config["dialogue_agent"].get("provider") or os.environ.get("LLM_PROVIDER") or "test"
            primary_llm_model = game_agent_config["dialogue_agent"].get("model") or os.environ.get("LLM_MODEL") or "test"
        elif "lifecycle_agent" in game_agent_config:
            primary_llm_provider = game_agent_config["lifecycle_agent"].get("provider") or os.environ.get("LLM_PROVIDER") or "test"
            primary_llm_model = game_agent_config["lifecycle_agent"].get("model") or os.environ.get("LLM_MODEL") or "test"
        else:
            primary_llm_provider = os.environ.get("LLM_PROVIDER") or "test"
            primary_llm_model = os.environ.get("LLM_MODEL") or "test"
        
        logger.info(f"Using LLM config for game agents: {primary_llm_provider}/{primary_llm_model}")
        
        try:
            # Use the dedicated MemoryAgent for experiments
            exp_memory_agent = self.exp_memory_agent
            # Configure summarizer if provided
            try:
                if self._summary_provider or self._summary_model:
                    exp_memory_agent.set_memory_summary_llm(self._summary_provider, self._summary_model)
            except Exception:
                pass

            logger.info("Initializing GameLoopManager with per-agent configs: %s", game_agent_config)
            game_loop = GameLoopManager(
                exp_memory_agent,
                sse_manager=sse_manager,
                stop_event=stop_event,
                llm_provider=primary_llm_provider,
                llm_model=primary_llm_model,
                agent_llm_configs=game_agent_config,
                reputation_enabled=reputation_enabled,
            )
            # If config specifies explicit time periods, honor them in experiment mode
            try:
                sess_cfg = self.config.get("session_config", {}) if hasattr(self, "config") else {}
                periods = sess_cfg.get("time_periods_per_day")
                if isinstance(periods, list) and periods:
                    game_loop.phases = periods
                    game_loop.current_phase = periods[0]
                    logger.info(f"Overriding phases from config: {periods}")
            except Exception:
                pass
            
            # Set current session: try to load first; only create if not found
            if not exp_memory_agent.current_session or exp_memory_agent.current_session.session_id != session_id:
                loaded = False
                try:
                    loaded = bool(exp_memory_agent.load_session(session_id))
                except Exception:
                    loaded = False
                if not loaded:
                    exp_memory_agent.create_session(session_id=session_id, game_settings=self.default_settings)
            
            session = exp_memory_agent.current_session
            
            # Handle continue mode
            continue_from_day = None
            if os.environ.get("EXPERIMENTAL_CONTINUE_MODE") == "1":
                try:
                    continue_from_day = int(os.environ.get("EXPERIMENTAL_CONTINUE_DAY", "1"))
                    logger.info(f"Continue mode: Resuming from day {continue_from_day}")
                    
                    # Verify the session has data for the target day
                    day_data = exp_memory_agent.db_manager.get_day(session_id, continue_from_day)
                    if not day_data:
                        logger.warning(f"No data found for day {continue_from_day} in session {session_id}, starting from day 1")
                        continue_from_day = None
                    else:
                        # Update session to current day for continuation
                        if session:
                            session.current_day = continue_from_day
                        logger.info(f"Session {session_id} restored to day {continue_from_day}")
                except Exception as e:
                    logger.warning(f"Failed to setup continue mode: {e}, starting from day 1")
                    continue_from_day = None
            
            # Set the starting day
            game_loop.current_day = continue_from_day if continue_from_day else (session.current_day if session else 1)
            
            logger.info(f"Game loop initialized for session {session_id}, starting at day {game_loop.current_day}")
            
            # Run the specified number of days
            days_completed = 0
            for day in range(duration_days):
                if stop_event.is_set():
                    break
                
                # Capture current day before the game loop advances it at end-of-day
                current_day_label = game_loop.current_day
                day_start_time = time.time()
                logger.info(f"Session {session_id}: Starting day {current_day_label}")
                
                try:
                    # Run day cycle with metrics collection
                    import asyncio
                    asyncio.run(game_loop.run_day_cycle())
                    
                    day_duration = time.time() - day_start_time
                    collector.record_metric("day_completion_time", day_duration, {
                        "day": current_day_label,
                        "session_id": session_id
                    })
                    
                    logger.info(f"Session {session_id}: Completed day {current_day_label} in {day_duration:.2f}s")
                    
                    # Advance time
                    exp_memory_agent.advance_time(new_day=current_day_label)
                    days_completed += 1
                    
                    # Log periodic summary every day
                    collector.log_periodic_summary()
                    
                except Exception as e:
                    logger.exception(f"Error during day {game_loop.current_day}: {e}")
                    collector.record_metric("day_error", 1, {
                        "day": game_loop.current_day,
                        "error": str(e),
                        "session_id": session_id
                    })
                    break
            
            total_duration = time.time() - session_start_time
            
            # Record final metrics
            collector.record_metric("session_total_duration", total_duration, {
                "days_completed": days_completed,
                "session_id": session_id
            })
            
            # Export metrics
            collector.export_json()
            
            logger.info(f"Session {session_id} completed: {days_completed}/{duration_days} days in {total_duration:.2f}s")
            
            return {
                "success": True,
                "session_id": session_id,
                "days_completed": days_completed,
                "total_duration": total_duration,
                "metrics_summary": collector.get_summary_stats()
            }
            
        except Exception as e:
            logger.exception(f"Fatal error in game session {session_id}: {e}")
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e)
            }
    
    def run_experiment(self, experiment_name: str, variant_id: Optional[str] = None, resume: bool = False) -> Dict[str, Any]:
        """Run a complete experiment with all variants or a specific variant
        
        Args:
            experiment_name: Name of the experiment from config
            variant_id: Optional specific variant to run (runs all if None)
            resume: If True, don't clear database before running (resume from current state)
            
        Returns:
            Dict with experiment results
        """
        if experiment_name not in self.config["experiments"]:
            logger.error(f"Experiment not found: {experiment_name}")
            return {"success": False, "error": f"Experiment '{experiment_name}' not found"}
        
        experiment = self.config["experiments"][experiment_name]
        logger.info(f"Starting experiment: {experiment['name']}")
        
        results = {
            "experiment_name": experiment_name,
            "experiment_description": experiment["description"],
            "variants": {},
            "start_time": datetime.utcnow().isoformat(),
            "success": True
        }
        
        duration_days = self.config.get("session_config", {}).get("duration_days", 2)
        
        # Filter variants if specific variant_id is provided
        variants_to_run = [v for v in experiment["variants"] if variant_id is None or v["id"] == variant_id]
        
        if variant_id and not variants_to_run:
            logger.error(f"Variant '{variant_id}' not found in experiment '{experiment_name}'")
            return {"success": False, "error": f"Variant '{variant_id}' not found in experiment '{experiment_name}'"}
        
        for variant in variants_to_run:
            curr_variant_id = variant["id"]  # This is always a string
            variant_name = variant["name"]
            
            logger.info(f"Running variant: {variant_name}")
            
            try:
                # Apply LLM configuration and get game agent config
                game_agent_config = self._apply_llm_config(variant)
                
                # Create session
                fixed_session_id = variant.get("config", {}).get("session_id")
                session_id = self._create_session(
                    experiment_name, 
                    curr_variant_id, 
                    fixed_session_id=fixed_session_id,
                    resume=resume
                )
                
                # Initialize metrics collector for this variant
                self.metrics_collector = init_metrics_collector(
                    f"{experiment_name}_{curr_variant_id}", 
                    session_id
                )
                
                # Run the game session with LLM configuration
                session_result = self._run_game_session(session_id, duration_days, game_agent_config, reputation_enabled=self._reputation_enabled)
                
                results["variants"][curr_variant_id] = {
                    "name": variant_name,
                    "session_id": session_id,
                    "config": variant["config"],
                    "result": session_result
                }
                
                if not session_result["success"]:
                    results["success"] = False
                
                logger.info(f"Variant {variant_name} completed")
                
            except Exception as e:
                logger.exception(f"Error running variant {variant_name}: {e}")
                results["variants"][variant_id] = {
                    "name": variant_name,
                    "error": str(e),
                    "success": False
                }
                results["success"] = False
        
        results["end_time"] = datetime.utcnow().isoformat()
        
        # Save experiment results
        results_file = f"experiment_results_{experiment_name}_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Experiment {experiment_name} completed. Results saved to {results_file}")
        return results
    
    def list_experiments(self):
        """List available experiments"""
        print("Available experiments:")
        for exp_name, exp_config in self.config["experiments"].items():
            print(f"  {exp_name}: {exp_config['name']}")
            print(f"    Description: {exp_config['description']}")
            print(f"    Variants: {len(exp_config['variants'])}")
            for variant in exp_config["variants"]:
                print(f"      - {variant['id']}: {variant['name']}")
            print()

def main():
    _setup_experiment_logging()
    parser = argparse.ArgumentParser(description="Run experimental game sessions")
    parser.add_argument("--config", default="experimental_config.json", 
                       help="Path to experimental config file")
    parser.add_argument("--experiment", help="Experiment name to run")
    parser.add_argument("--variant", help="Specific variant ID to run (defaults to all variants)")
    parser.add_argument("--resume", action="store_true", help="Resume experiment without clearing database")
    parser.add_argument("--list", action="store_true", help="List available experiments")
    # Simple (non-experiment) run options
    parser.add_argument("--simple", action="store_true", help="Run a simple non-experiment session")
    parser.add_argument("--days", type=int, default=1, help="Days to run for simple mode")
    parser.add_argument("--session-id", dest="session_id", help="Fixed session ID for simple mode")
    parser.add_argument("--provider", dest="provider", help="LLM provider override for simple mode")
    parser.add_argument("--model", dest="model", help="LLM model override for simple mode")
    
    args = parser.parse_args()
    
    runner = ExperimentalRunner(args.config)
    
    if args.list:
        runner.list_experiments()
        return
    
    if args.simple:
        # Minimal non-experiment run (DRY with experiment infra)
        def _run_simple():
            # Clear and set log already handled by basicConfig
            from threading import Event
            import asyncio as _asyncio
            # Optionally purge existing session data when a fixed id is provided
            sid = args.session_id or None
            if sid:
                try:
                    runner.exp_memory_agent.db_manager.delete_session_data(sid)
                except Exception:
                    pass
            # Create or reset session
            if sid:
                # Prefer loading existing; else create new
                try:
                    if not runner.exp_memory_agent.load_session(sid):
                        runner.exp_memory_agent.create_session(session_id=sid, game_settings=runner.default_settings)
                except Exception:
                    runner.exp_memory_agent.create_session(session_id=sid, game_settings=runner.default_settings)
            else:
                runner.exp_memory_agent.create_session(session_id=None, game_settings=runner.default_settings)
            # Initialize GameLoopManager with optional provider/model overrides
            primary_provider = args.provider or os.environ.get("LLM_PROVIDER")
            primary_model = args.model or os.environ.get("LLM_MODEL")
            glm = GameLoopManager(
                runner.exp_memory_agent,
                sse_manager=SSEManager() if os.environ.get("EXPERIMENTAL_MODE") else None,
                stop_event=Event(),
                llm_provider=primary_provider,
                llm_model=primary_model,
                agent_llm_configs={},
            )
            # Use config time periods if present
            sess_cfg = runner.config.get("session_config", {}) if hasattr(runner, "config") else {}
            if sess_cfg.get("time_periods_per_day"):
                glm.phases = sess_cfg.get("time_periods_per_day")
            # Run specified days
            for _ in range(max(1, int(args.days))):
                _asyncio.run(glm.run_day_cycle())
            print("Simple session completed.")
        _run_simple()
        return
    
    if not args.experiment:
        print("Please specify an experiment with --experiment or use --simple for a quick run")
        runner.list_experiments()
        return
    
    # Run the experiment
    results = runner.run_experiment(
        args.experiment,
        variant_id=args.variant,
        resume=args.resume
    )
    
    if results["success"]:
        print(f"\nExperiment '{args.experiment}' completed successfully!")
        print(f"Results saved to experiment results file")
    else:
        print(f"\nExperiment '{args.experiment}' failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
