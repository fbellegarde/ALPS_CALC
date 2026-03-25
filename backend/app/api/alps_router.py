from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, validator
from typing import List, Dict, Any
from app.services.alps_service import AlpsFlowEngine
import uuid
import os
import json
import sqlite3
import io
import pandas as pd
from datetime import datetime

router = APIRouter()
alps_engine = AlpsFlowEngine()

# Input Validation Model
class ShiftInput(BaseModel):
    Date: str
    Shift: str
    Volume: Any  # Accept Any initially to catch empty strings
    Target_Handoff_Buffer: Any = 3000.0
    Diluted_Rate_TPH: Any = 14.6
    Shift_Length_Hrs: Any = 10.0
    Scheduled_HC: Any
    Absence_Pct: Any = 0.10
    VET_Net_Hrs: Any = 0.0
    VTO_Net_Hrs: Any = 0.0
    Misc_Labor_Share_Hrs: Any = 0.0

    # CRITICAL FIX: Pydantic Validator to safely convert empty strings to 0.0
    @validator('*', pre=True)
    def empty_string_to_zero(cls, v):
        if v == "" or v is None:
            return 0.0
        # If it's a date or shift string, pass it through
        if isinstance(v, str) and not v.replace('.', '', 1).isdigit():
            return v
        # Ensure numerical values become floats
        try:
            return float(v)
        except ValueError:
            return v

# ENHANCEMENT: Payload now accepts the global initial_backlog property
class AlpsPredictionRequest(BaseModel):
    initial_backlog: float = 0.0
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
                
                # ENHANCEMENT: Dual-Key mapping to ensure bulletproof data transfer 
                # between the new Vue TPH input and the Math Engine
                "Target Handoff Buffer": s.Target_Handoff_Buffer,
                "Target_Handoff_Buffer": s.Target_Handoff_Buffer,
                
                "Diluted Rate (TPH)": s.Diluted_Rate_TPH,
                "Diluted_Rate_TPH": s.Diluted_Rate_TPH,
                
                "Shift Length (Hrs)": s.Shift_Length_Hrs,
                "Shift_Length_Hrs": s.Shift_Length_Hrs,
                
                "Scheduled HC": s.Scheduled_HC,
                "Scheduled_HC": s.Scheduled_HC,
                
                "Absence Pct": s.Absence_Pct,
                "Absence_Pct": s.Absence_Pct,
                
                "VET Net (Hrs)": s.VET_Net_Hrs,
                "VET_Net_Hrs": s.VET_Net_Hrs,
                
                "VTO Net (Hrs)": s.VTO_Net_Hrs,
                "VTO_Net_Hrs": s.VTO_Net_Hrs,
                
                "Misc/Labor Share (Hrs)": s.Misc_Labor_Share_Hrs,
                "Misc_Labor_Share_Hrs": s.Misc_Labor_Share_Hrs
            })
        
        # Pass the initial backlog from the Vue UI directly into the Engine
        result = alps_engine.calculate_cascade(shift_dicts, initial_backlog=request.initial_backlog)
        return {"status": "success", "data": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/simulation/{sim_id}/chat")
async def get_simulation_chat(sim_id: str):
    # Stabilized path anchoring to the backend folder
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_path, "uploads", "simulations", sim_id, "reddit_simulation.db")
    
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

# RESTORED: Endpoint to list all active simulations for the Chime sidebar
@router.get("/simulations")
async def list_active_simulations():
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sim_dir = os.path.join(base_path, "uploads", "simulations")
    
    sims = []
    if os.path.exists(sim_dir):
        # Get all folders starting with 'sim_'
        folders = [f for f in os.listdir(sim_dir) if f.startswith("sim_")]
        
        # CRITICAL UX FIX: Sort folders by modification time so the newest simulation is always at the TOP
        folders.sort(key=lambda x: os.path.getmtime(os.path.join(sim_dir, x)), reverse=True)
        
        for folder in folders:
            # Check for database to confirm it's an active/ready sim
            db_path = os.path.join(sim_dir, folder, "reddit_simulation.db")
            sims.append({
                "simulation_id": folder,
                "status": "LIVE" if os.path.exists(db_path) else "PREP"
            })
    return sims
    
@router.post("/simulation/{sim_id}/send")
async def send_simulation_command(sim_id: str, payload: Dict[str, Any]):
    # Stabilized path anchoring
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    command_dir = os.path.join(base_path, "uploads", "simulations", sim_id, "ipc_commands")
    
    # CRITICAL FIX: Ensure the directory exists dynamically to prevent FAILED PATH crashes
    os.makedirs(command_dir, exist_ok=True)
    
    try:
        cmd_id = str(uuid.uuid4())
        file_path = os.path.join(command_dir, f"cmd_{cmd_id}.json")
        with open(file_path, "w") as f:
            json.dump(payload, f)
        return {"status": "success", "message": "Command Dispatched"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# ENHANCEMENT: AMAZON EXPORT CSV PARSER
# ==========================================
@router.post("/upload_roster")
async def parse_roster_csv(file: UploadFile = File(...)):
    """
    Ingests the multi-table Amazon Attendance Summary CSV.
    Extracts the Outbound summary and calculates flow parameters.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    try:
        contents = await file.read()
        content_str = contents.decode('utf-8')
        lines = content_str.split('\n')
        
        export_date_str = "2026-03-22"
        shift_val = "Day"
        outbound_sched = 0
        outbound_on_prem = 0
        
        # 1. Extract Export Date
        for line in lines:
            if line.startswith("Export Date:"):
                # Example: Export Date: 3/22/2026, 3:29:07 AM
                raw_date = line.split("Export Date:")[1].split(",")[0].strip()
                try:
                    dt = datetime.strptime(raw_date, "%m/%d/%Y")
                    export_date_str = dt.strftime("%Y-%m-%d")
                    # Auto-detect shift based on export time
                    if "PM" in line and int(line.split(" ")[2].split(":")[0]) >= 4:
                        shift_val = "Night"
                except Exception:
                    pass
                break
                
        # 2. Extract Outbound Summary Row
        for line in lines:
            if line.startswith("Outbound,"):
                parts = line.split(",")
                # Line format: Outbound,On Premise,Scheduled,Attendance %,LP %,Diff
                try:
                    outbound_on_prem = int(parts[1]) if parts[1].strip() else 0
                except ValueError:
                    outbound_on_prem = 0
                    
                try:
                    outbound_sched = int(parts[2]) if parts[2].strip() else 0
                except ValueError:
                    outbound_sched = 0
                break
                
        # 3. Calculate True Variance (Absence vs. VET)
        absence_pct = 0.0
        vet_hrs = 0.0
        
        if outbound_sched > outbound_on_prem:
            # We have missing headcount
            absence_pct = round((outbound_sched - outbound_on_prem) / outbound_sched, 2)
        elif outbound_on_prem > outbound_sched:
            # We have extra headcount (VET or Flex Pickups). Assume 10 hr shift for baseline.
            vet_hrs = (outbound_on_prem - outbound_sched) * 10.0

        # 4. Construct ALPS Input
        shift_data = {
            "Date": export_date_str,
            "Shift": shift_val,
            "Volume": 0,  # Needs manual entry in UI as it's not in the attendance export
            "Scheduled_HC": outbound_sched,
            "Absence_Pct": absence_pct,
            "VET_Net_Hrs": vet_hrs,
            "VTO_Net_Hrs": 0.0,
            "Misc_Labor_Share_Hrs": 0.0,
            "Target_Handoff_Buffer": 3000,
            "Diluted_Rate_TPH": 14.6,
            "Shift_Length_Hrs": 10.0
        }
        
        return {"status": "success", "data": [shift_data]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse CSV: {str(e)}")