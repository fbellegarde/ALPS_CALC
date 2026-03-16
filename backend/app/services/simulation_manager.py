"""
AMAZON NACF ALPS SIMULATION MANAGER
Manages the Digital Twin Flow Simulation using Machine Learning & LLM Personas.
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from .alps_service import AlpsFlowEngine  # <-- INJECTED ALPS ENGINE

logger = get_logger('mirofish.simulation')

class SimulationStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"

class PlatformType(str, Enum):
    AMAZON_CHIME = "chime" # Replaced Twitter/Reddit with Amazon internal comms
    AMAZON_SLACK = "slack"

@dataclass
class SimulationState:
    simulation_id: str
    project_id: str
    graph_id: str
    
    status: SimulationStatus = SimulationStatus.CREATED
    
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    
    config_generated: bool = False
    config_reasoning: str = ""
    
    current_round: int = 0
    chime_status: str = "not_started"
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "chime_status": self.chime_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }

class SimulationManager:
    SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../../uploads/simulations')
    
    # --- AMAZON NACF LEADERSHIP PERSONAS (KITCHEN SINK VERSION) ---
    AMAZON_NACF_AGENTS = [
        {
            "name": "Senior_OM_Sarah",
            "username": "Senior_OM_Sarah",
            "role": "Senior Operations Manager",
            "bio": "Senior Operations Manager focused on NACF outbound flow and CPU protection.",
            "mbti": "ENTJ", "gender": "female", "age": 35, "country": "USA", "state": "WA", "city": "Seattle",
            "location": "Seattle, WA", "education": "MBA", "occupation": "Operations",
            "interests": ["Logistics", "Optimization"], "traits": ["Analytical", "Assertive"],
            "persona": "You are the Senior OM. Your goal is to hit the building's 100k ship goal and protect CPU."
        },
        {
            "name": "Flow_Lead_Fernando",
            "username": "Flow_Lead_Fernando",
            "role": "Central Flow Lead",
            "bio": "Central Flow Lead managing ALPS real-time data and WIP handoff buffers.",
            "mbti": "INTJ", "gender": "male", "age": 28, "country": "USA", "state": "WA", "city": "Seattle",
            "location": "Seattle, WA", "education": "Masters", "occupation": "Logistics",
            "interests": ["Data Science", "Flow"], "traits": ["Strategic", "Direct"],
            "persona": "You operate the ALPS Engine. You protect the Target WIP Buffer at all costs."
        },
        {
            "name": "Pack_AM_Alex",
            "username": "Pack_AM_Alex",
            "role": "Pack Area Manager",
            "bio": "Pack Area Manager overseeing AFE and Singles productivity.",
            "mbti": "ESTJ", "gender": "male", "age": 30, "country": "USA", "state": "WA", "city": "Seattle",
            "location": "Seattle, WA", "education": "BS", "occupation": "Area Manager",
            "interests": ["Leadership", "Throughput"], "traits": ["Tactical", "Protective"],
            "persona": "You manage the AFE walls. You constantly fight against conveyance starvation."
        },
        {
            "name": "Pick_AM_Marcus",
            "username": "Pick_AM_Marcus",
            "role": "Pick Area Manager",
            "bio": "Pick Area Manager managing the AR floor and outbound induction faucet.",
            "mbti": "ISTJ", "gender": "male", "age": 32, "country": "USA", "state": "WA", "city": "Seattle",
            "location": "Seattle, WA", "education": "BS", "occupation": "Area Manager",
            "interests": ["Inventory", "Metrics"], "traits": ["Methodical", "Metric-driven"],
            "persona": "You control the faucet. You are highly protective of your headcount to prevent starvation."
        },
        {
            "name": "Dock_AM_David",
            "username": "Dock_AM_David",
            "role": "Ship Dock Area Manager",
            "bio": "Ship Dock Area Manager ensuring trailer departures and CPT compliance.",
            "mbti": "ESTP", "gender": "male", "age": 29, "country": "USA", "state": "WA", "city": "Seattle",
            "location": "Seattle, WA", "education": "BA", "occupation": "Area Manager",
            "interests": ["Transportation", "Efficiency"], "traits": ["Urgent", "Reactive"],
            "persona": "You manage the trailers. Your only concern is Critical Pull Times (CPTs)."
        }
    ]

    def __init__(self):
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        self._simulations: Dict[str, SimulationState] = {}
        self.alps_engine = AlpsFlowEngine() # Initialize the ML Math Engine
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        state.updated_at = datetime.now().isoformat()
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            chime_status=data.get("chime_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        ) # <--- THIS MUST BE A PARENTHESIS, NOT A CURLY BRACE
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(self, project_id: str, graph_id: str) -> SimulationState:
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            status=SimulationStatus.CREATED,
        )
        self._save_simulation_state(state)
        logger.info(f"Created NACF Simulation: {simulation_id}")
        return state
    
    def prepare_simulation(self, simulation_id: str, simulation_requirement: str, document_text: str, progress_callback: Optional[callable] = None) -> SimulationState:
        state = self._load_simulation_state(simulation_id)
        if not state: raise ValueError("Sim Not Found")
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            sim_dir = self._get_simulation_dir(simulation_id)
            
            # 1. Save Profiles
            profiles_path = os.path.join(sim_dir, "reddit_profiles.json")
            with open(profiles_path, 'w', encoding='utf-8') as f:
                json.dump(self.AMAZON_NACF_AGENTS, f, ensure_ascii=False, indent=2)
            
            # 2. Build REDDIT-COMPATIBLE Config
            # This satisfies the "Agent Quantity" check and gives them a "Subreddit" to chat in.
            reddit_config = {
                "simulation_id": simulation_id,
                "start_time": datetime.now().isoformat(),
                "duration_hours": 72,
                "communities": [
                    {
                        "name": "Amazon_NACF_Ops_Center",
                        "description": "Real-time coordination for Outbound Flow and ALPS metrics.",
                        "members": [a["username"] for a in self.AMAZON_NACF_AGENTS],
                        "initial_threads": [
                            {
                                "title": "ALPS FLOW ALERT: Deficit Detected",
                                "content": "Flow Lead Fernando: ALPS is predicting a deficit for tonight. We need to discuss labor sharing to protect the 5000 WIP buffer.",
                                "author": "Flow_Lead_Fernando"
                            }
                        ]
                    }
                ],
                "agents": [
                    {
                        "username": a["username"],
                        "activity_level": 1.0,
                        "responsiveness": 1.0
                    } for a in self.AMAZON_NACF_AGENTS
                ]
            }
            
            with open(os.path.join(sim_dir, "simulation_config.json"), 'w', encoding='utf-8') as f:
                json.dump(reddit_config, f, ensure_ascii=False, indent=2)
            
            state.profiles_count = len(self.AMAZON_NACF_AGENTS)
            state.config_generated = True
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            return state
        except Exception as e:
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise

    # Keep helper methods for API compatibility
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        return self._load_simulation_state(simulation_id)
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        sim_dir = self._get_simulation_dir(simulation_id)
        # Always return the Amazon profiles regardless of what the old MiroFish UI requests
        profile_path = os.path.join(sim_dir, "amazon_leadership_profiles.json")
        if not os.path.exists(profile_path):
            return []
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_run_instructions(self, simulation_id: str) -> Dict[str, Any]:
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "chime": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}"
            },
            "instructions": f"1. Activate environment\n2. Run NACF Flow Simulation: python {scripts_dir}/run_reddit_simulation.py --config {config_path}"
        }