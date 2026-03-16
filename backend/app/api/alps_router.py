from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.alps_service import AlpsFlowEngine
import uuid
from typing import Dict, Any, List
import os
import json
import sqlite3

router = APIRouter()
alps_engine = AlpsFlowEngine()

# Input Validation Model
class ShiftInput(BaseModel):
    Date: str
    Shift: str
    Volume: float
    Target_Handoff_Buffer: float = 5000.0
    Diluted_Rate_TPH: float = 14.6
    Shift_Length_Hrs: float = 10.0
    Scheduled_HC: float
    Absence_Pct: float = 0.10
    VET_Net_Hrs: float = 0.0
    VTO_Net_Hrs: float = 0.0
    Misc_Labor_Share_Hrs: float = 0.0

class AlpsPredictionRequest(BaseModel):
    shifts: List[ShiftInput]

@router.post("/predict")
async def predict_flow(request: AlpsPredictionRequest):
    try:
        # Convert Pydantic models to dicts for the engine
        shift_dicts = []
        for s in request.shifts:
            shift_dicts.append({
                "Date": s.Date,
                "Shift": s.Shift,
                "Volume": s.Volume,
                "Target Handoff Buffer": s.Target_Handoff_Buffer,
                "Diluted Rate (TPH)": s.Diluted_Rate_TPH,
                "Shift Length (Hrs)": s.Shift_Length_Hrs,
                "Scheduled HC": s.Scheduled_HC,
                "Absence Pct": s.Absence_Pct,
                "VET Net (Hrs)": s.VET_Net_Hrs,
                "VTO Net (Hrs)": s.VTO_Net_Hrs,
                "Misc/Labor Share (Hrs)": s.Misc_Labor_Share_Hrs
            })
        
        result = alps_engine.calculate_cascade(shift_dicts)
        return {"status": "success", "data": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/simulation/{sim_id}/chat")
async def get_simulation_chat(sim_id: str):
    # This path must match your simulation upload directory
    db_path = os.path.join(os.getcwd(), "uploads", "simulations", sim_id, "reddit_simulation.db")
    
    if not os.path.exists(db_path):
        return {"status": "error", "message": "Simulation database not found"}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Query the 'trace' table for all LLM responses (Interviews and Posts)
        cursor.execute("SELECT user_id, info, created_at FROM trace ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        
        chat_logs = []
        for row in rows:
            user_id, info_json, timestamp = row
            info = json.loads(info_json)
            chat_logs.append({
                "agent_id": user_id,
                "message": info.get("response", info.get("content", "")),
                "time": timestamp
            })
        conn.close()
        return {"status": "success", "data": chat_logs}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@router.post("/simulation/{sim_id}/send")
async def send_simulation_command(sim_id: str, payload: Dict[str, Any]):
    # Get the project root folder instead of the current working directory
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    command_dir = os.path.join(base_path, "uploads", "simulations", sim_id, "ipc_commands")
    
    if not os.path.exists(command_dir):
        # Professional Debugging: Let's see exactly what path we were looking for
        print(f"FAILED PATH: {command_dir}")
        return {"status": "error", "message": f"IPC Path Missing: {sim_id}"}
    
    sims = []
    # Get all folders starting with 'sim_'
    for folder in os.listdir(sim_dir):
        if folder.startswith("sim_"):
            # Check for database to confirm it's an active/ready sim
            db_path = os.path.join(sim_dir, folder, "reddit_simulation.db")
            sims.append({
                "simulation_id": folder,
                "status": "LIVE" if os.path.exists(db_path) else "PREP"
            })
    return sims