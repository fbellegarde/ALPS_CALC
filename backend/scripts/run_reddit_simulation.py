"""
OASIS Reddit Simulation Preset Script
This script reads parameters from the configuration file to execute a fully automated simulation.

Features:
- Maintains environment alive after simulation completion (Wait Command Mode).
- Supports receiving Interview commands via IPC.
- Supports single Agent interviews and batch interviews.
- Supports remote environment shutdown commands.

Usage:
    python run_reddit_simulation.py --config /path/to/simulation_config.json
    python run_reddit_simulation.py --config /path/to/simulation_config.json --no-wait  # Close immediately
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

# Global variables for signal handling
_shutdown_event = None
_cleanup_done = False

# Setup project paths
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# Load .env file from project root (containing LLM_API_KEY, etc.)
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)
else:
    _backend_env = os.path.join(_backend_dir, '.env')
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)

import re

class UnicodeFormatter(logging.Formatter):
    """Custom formatter to convert Unicode escape sequences into readable characters."""
    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')
    
    def format(self, record):
        result = super().format(record)
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)
        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)

class MaxTokensWarningFilter(logging.Filter):
    """Filters camel-ai warnings regarding max_tokens (we let the model decide)."""
    def filter(self, record):
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True

# Apply filter immediately
logging.getLogger().addFilter(MaxTokensWarningFilter())

def setup_oasis_logging(log_dir: str):
    """Configures OASIS logging with fixed-name log files."""
    os.makedirs(log_dir, exist_ok=True)
    
    # Clean up old logs
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass
    
    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")
    
    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }
    
    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False

try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_reddit_agent_graph
    )
except ImportError as e:
    print(f"Error: Missing dependencies {e}")
    print("Please install via: pip install oasis-ai camel-ai")
    sys.exit(1)

# IPC Constants
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"

class IPCHandler:
    """Handles Inter-Process Communication commands."""
    def __init__(self, simulation_dir: str, env, agent_graph):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def update_status(self, status: str):
        """Update the environment status file."""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """Check for pending commands in the IPC directory."""
        if not os.path.exists(self.commands_dir): return None
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        return None
    
    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """Send command response and cleanup the command file."""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
        
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str) -> bool:
        """Process a single agent interview command."""
        try:
            agent = self.agent_graph.get_agent(agent_id)
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            await self.env.step({agent: interview_action})
            result = self._get_interview_result(agent_id)
            self.send_response(command_id, "completed", result=result)
            print(f"  Interview completed: agent_id={agent_id}")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"  Interview failed: agent_id={agent_id}, error={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False
    
    async def handle_batch_interview(self, command_id: str, interviews: List[Dict]) -> bool:
        """Process multiple agent interviews in parallel."""
        try:
            actions = {}
            agent_ids = []
            for item in interviews:
                agent_id = item.get("agent_id")
                prompt = item.get("prompt", "")
                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(action_type=ActionType.INTERVIEW, action_args={"prompt": prompt})
                    agent_ids.append(agent_id)
                except Exception as e:
                    print(f"  Warning: Could not retrieve Agent {agent_id}: {e}")
            
            if not actions:
                self.send_response(command_id, "failed", error="No valid agents found.")
                return False
            
            await self.env.step(actions)
            results = {aid: self._get_interview_result(aid) for aid in agent_ids}
            self.send_response(command_id, "completed", result={"interviews_count": len(results), "results": results})
            print(f"  Batch Interview completed: {len(results)} Agents processed.")
            return True
        except Exception as e:
            self.send_response(command_id, "failed", error=str(e))
            return False

    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """Fetch latest interview record from simulation database."""
        db_path = os.path.join(self.simulation_dir, "reddit_simulation.db")
        result = {"agent_id": agent_id, "response": None, "timestamp": None}
        if not os.path.exists(db_path): return result
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, info, created_at FROM trace WHERE action = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1", (ActionType.INTERVIEW.value, agent_id))
            row = cursor.fetchone()
            if row:
                _, info_json, created_at = row
                info = json.loads(info_json) if info_json else {}
                result["response"] = info.get("response", info)
                result["timestamp"] = created_at
            conn.close()
        except Exception as e:
            print(f"  Failed to read interview result: {e}")
        return result

    async def process_commands(self) -> bool:
        """Poll and process incoming IPC commands."""
        command = self.poll_command()
        if not command: return True
        cid = command.get("command_id")
        ctype = command.get("command_type")
        args = command.get("args", {})
        print(f"\nReceived IPC Command: {ctype}, id={cid}")
        if ctype == CommandType.INTERVIEW:
            await self.handle_interview(cid, args.get("agent_id", 0), args.get("prompt", ""))
            return True
        elif ctype == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(cid, args.get("interviews", []))
            return True
        elif ctype == CommandType.CLOSE_ENV:
            print("Received environment shutdown command.")
            self.send_response(cid, "completed", result={"message": "Environment is closing."})
            return False
        else:
            self.send_response(cid, "failed", error=f"Unknown command type: {ctype}")
            return True

class RedditSimulationRunner:
    """Reddit Digital Twin Runner."""
    AVAILABLE_ACTIONS = [
        ActionType.LIKE_POST, ActionType.DISLIKE_POST, ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT, ActionType.LIKE_COMMENT, ActionType.DISLIKE_COMMENT,
        ActionType.SEARCH_POSTS, ActionType.SEARCH_USER, ActionType.TREND,
        ActionType.REFRESH, ActionType.DO_NOTHING, ActionType.FOLLOW, ActionType.MUTE,
    ]
    
    def __init__(self, config_path: str, wait_for_commands: bool = True):
        self.config_path = config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands

    def _create_model(self):
        """Initializes SARA Core via environment variables."""
        llm_api_key = os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_model = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
        
        if llm_api_key: os.environ["OPENAI_API_KEY"] = llm_api_key
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("Missing API Key. Please set LLM_API_KEY in .env file.")
        if llm_base_url: os.environ["OPENAI_API_BASE_URL"] = llm_base_url
        
        print(f"LLM Configuration: model={llm_model}, base_url={llm_base_url[:40] if llm_base_url else 'Default'}...")
        return ModelFactory.create(model_platform=ModelPlatformType.OPENAI, model_type=llm_model)

    async def run(self, max_rounds: int = None):
        """Executes the simulation loop."""
        print("=" * 60)
        print("🚀 OASIS Amazon Digital Twin Simulation")
        print(f"Config: {self.config_path}")
        print(f"Sim ID: {self.config.get('simulation_id', 'unknown')}")
        print(f"Wait Command Mode: {'Enabled' if self.wait_for_commands else 'Disabled'}")
        print("=" * 60)
        
        agents_list = self.config.get("agents", [])
        time_cfg = self.config.get("time_config", {})
        total_rounds = min((time_cfg.get("total_simulation_hours", 72) * 60) // time_cfg.get("minutes_per_round", 30), max_rounds or 9999)
        
        print(f"\nSimulation Parameters:")
        print(f"  - Total Rounds: {total_rounds}")
        print(f"  - Agent Quantity: {len(agents_list)}")
        
        print("\nInitializing LLM Model (SARA)...")
        model = self._create_model()
        
        print("Loading Agent Profiles...")
        profile_path = os.path.join(self.simulation_dir, "reddit_profiles.json")
        self.agent_graph = await generate_reddit_agent_graph(profile_path=profile_path, model=model, available_actions=self.AVAILABLE_ACTIONS)
        
        db_path = os.path.join(self.simulation_dir, "reddit_simulation.db")
        if os.path.exists(db_path): os.remove(db_path)
        
        print("Creating OASIS Environment...")
        self.env = oasis.make(agent_graph=self.agent_graph, platform=oasis.DefaultPlatformType.REDDIT, database_path=db_path, semaphore=30)
        await self.env.reset()
        print("Initialization Complete.\n")
        
        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph)
        self.ipc_handler.update_status("running")

        # Dynamic Agent Discovery
        active_agents = []
        if hasattr(self.agent_graph, 'id_to_agent'):
            active_agents = list(self.agent_graph.id_to_agent.values())
        elif hasattr(self.agent_graph, 'agent_list'):
            active_agents = self.agent_graph.agent_list
        elif hasattr(self.agent_graph, 'agents'):
            active_agents = self.agent_graph.agents

        print("\nStarting Simulation Loop...")
        start_time = datetime.now()
        for round_num in range(total_rounds):
            actions = {agent: LLMAction() for agent in active_agents}
            await self.env.step(actions)
            if (round_num + 1) % 5 == 0 or round_num == 0:
                print(f"  Round {round_num + 1}/{total_rounds} complete - elapsed: {(datetime.now() - start_time).total_seconds():.1f}s")
        
        print(f"\nSimulation Cycle Complete! DB: {db_path}")
        
        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("ENTERING INTERACTIVE COMMAND MODE")
            print("Type 'interview' or 'batch_interview' to talk to the Triad.")
            print("Type 'close_env' to exit.")
            print("=" * 60)
            self.ipc_handler.update_status("alive")

            # --- NEW INTERACTIVE CONSOLE LOOP ---
            while not _shutdown_event.is_set():
                # Process IPC (Frontend commands)
                if not await self.ipc_handler.process_commands(): break

                # Listen for Terminal Input (User typing)
                try:
                    # Non-blocking input check using a tiny sleep and executor
                    loop = asyncio.get_event_loop()
                    user_input = await loop.run_in_executor(None, lambda: input("ALPS-COMMAND > ").strip())
                    
                    if user_input.lower() == 'close_env':
                        break
                    elif user_input.lower() == 'interview':
                        agent_id = input("Enter Agent ID (0-4): ")
                        prompt = input("Your question: ")
                        await self.ipc_handler.handle_interview("terminal_cmd", int(agent_id), prompt)
                    elif user_input.lower() == 'batch_interview':
                        prompt = input("Question for the whole Leadership Team: ")
                        batch = [{"agent_id": i, "prompt": prompt} for i in range(len(active_agents))]
                        await self.ipc_handler.handle_batch_interview("terminal_batch", batch)
                    else:
                        print(f"Unknown command: {user_input}")
                except EOFError:
                    break
                except Exception as e:
                    print(f"Input Error: {e}")

        self.ipc_handler.update_status("stopped")
        await self.env.close()
        print("Environment closed.")

async def main():
    parser = argparse.ArgumentParser(description='OASIS Amazon Simulation Runner')
    parser.add_argument('--config', type=str, required=True)
    parser.add_argument('--max-rounds', type=int, default=None)
    parser.add_argument('--no-wait', action='store_true', default=False)
    args = parser.parse_args()
    
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    simulation_dir = os.path.dirname(args.config) or "."
    setup_oasis_logging(os.path.join(simulation_dir, "log"))
    
    runner = RedditSimulationRunner(config_path=args.config, wait_for_commands=not args.no_wait)
    await runner.run(max_rounds=args.max_rounds)

def setup_signal_handlers():
    def signal_handler(signum, frame):
        global _cleanup_done
        print(f"\nReceived termination signal, exiting...")
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event: _shutdown_event.set()
        else: sys.exit(1)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    setup_signal_handlers()
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nProcess interrupted.")
    finally: print("Simulation process exited.")