import os
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Any
# Assuming ml_predictor is in the same directory structure we established
from app.services.ml_predictor import AlpsMachineLearning

class AlpsFlowEngine:
    def __init__(self, target_buffer=3000, diluted_tph=14.6):
        self.target_buffer = target_buffer # Defaulting to the BOS7 safe WIP barrier
        self.diluted_tph = diluted_tph
        self.ml_engine = AlpsMachineLearning()
        
        # Setup logging directory (Professional Standard: keeps outputs isolated)
        self.log_dir = os.path.join(os.getcwd(), "outputs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "alps_prediction_history.csv")

    # ENHANCEMENT: Accepts initial_backlog straight from the frontend
    def calculate_cascade(self, shift_data_list: List[Dict[str, Any]], initial_backlog: float = 0.0) -> List[Dict[str, Any]]:
        cascade_data = []
        # CRITICAL FIX: The pump prime is now seamlessly handled here
        rolling_backlog = initial_backlog
        log_entries = []

        # --- HISTORICAL TREND ANALYSIS ---
        current_trend = None
        streak_count = 0

        if os.path.exists(self.log_file):
            try:
                df_hist = pd.read_csv(self.log_file)
                if not df_hist.empty and 'Action_Category' in df_hist.columns:
                    last_actions = df_hist['Action_Category'].tolist()
                    if last_actions:
                        current_trend = last_actions[-1]
                        for act in reversed(last_actions):
                            if act == current_trend:
                                streak_count += 1
                            else:
                                break
            except Exception:
                pass 

        for shift in shift_data_list:
            # ENHANCEMENT: Bulletproof key extraction. Checks for both router formats and direct API formats.
            date_str = shift.get('Date', 'Unknown')
            shift_name = shift.get('Shift', 'Unknown')
            volume = float(shift.get('Volume', 0))
            sched_hc = float(shift.get('Scheduled_HC', shift.get('Scheduled HC', 0)))
            target_buffer = float(shift.get('Target_Handoff_Buffer', shift.get('Target Handoff Buffer', self.target_buffer)))
            shift_length = float(shift.get('Shift_Length_Hrs', shift.get('Shift Length (Hrs)', 10.0)))
            
            # CRITICAL FIX: Extracting the manual levers correctly
            vet = float(shift.get('VET_Net_Hrs', shift.get('VET Net (Hrs)', 0)))
            vto = float(shift.get('VTO_Net_Hrs', shift.get('VTO Net (Hrs)', 0)))
            misc_ls = float(shift.get('Misc_Labor_Share_Hrs', shift.get('Misc/Labor Share (Hrs)', 0)))
            
            # ENHANCEMENT: Extract the TPH directly from the Vue UI payload
            ui_tph = float(shift.get('Diluted_Rate_TPH', shift.get('Diluted Rate (TPH)', self.diluted_tph)))

            # Machine Learning Override
            try:
                day_of_week = pd.to_datetime(date_str).strftime('%a')
            except:
                day_of_week = 'Mon'
            
            ml_predictions = self.ml_engine.predict_shift_variance(day_of_week, volume, sched_hc)
            
            # ENHANCEMENT: Prioritize the UI TPH so you have absolute manual control over the baseline
            tph = ui_tph
            absence_pct = ml_predictions.get("Predicted_Absence", 0.10)

            # Phase 1: True Show Hours
            gross_hours = sched_hc * shift_length
            absence_hrs = gross_hours * absence_pct
            
            # Applying the manual levers directly to capacity
            show_hours = (gross_hours - absence_hrs) + vet - vto + misc_ls
            
            # Phase 2: Capacity & Demand
            daily_capacity = show_hours * tph
            workable_demand_vol = volume + rolling_backlog
            
            # Phase 3: WIP Protection Math
            actionable_volume = max(0, workable_demand_vol - target_buffer)
            daily_volume_delta = daily_capacity - actionable_volume
            daily_hours_delta = daily_volume_delta / tph if tph > 0 else 0

            # Phase 4: Executive Action & UI Color Mapping
            if daily_hours_delta >= 20:
                action = f"+{daily_hours_delta:.1f} Hrs"
                action_type = "VTO"  # Green in UI
                trend_type = "SURPLUS"
            elif daily_hours_delta <= -20:
                action = f"{daily_hours_delta:.1f} Hrs"
                action_type = "VET"  # Red in UI
                trend_type = "DEFICIT"
            else:
                action = f"BALANCED: {daily_hours_delta:.1f} Hrs"
                action_type = "BALANCED"
                trend_type = "BALANCED"

            planned_end_backlog = target_buffer if workable_demand_vol >= target_buffer else workable_demand_vol

            # --- TREND LOGIC ---
            if trend_type == current_trend:
                streak_count += 1
            else:
                current_trend = trend_type
                streak_count = 1

            if streak_count >= 7:
                feedback = f"CRITICAL: Compounding {current_trend} ({streak_count} shifts). High Burnout Risk."
            elif streak_count >= 3:
                feedback = f"Bullwhip Alert: {streak_count} consecutive {current_trend} shifts."
            else:
                feedback = f"New Trend: {current_trend} sequence started."

            # This dictionary MUST match the Vue Frontend exactly
            processed_shift = {
                "Date": date_str,
                "Shift": shift_name,
                "Total_Workable_Demand": int(workable_demand_vol),
                "Target_Buffer": int(target_buffer),
                "AI_Predicted_TPH": round(tph, 2),
                "AI_Predicted_Absence": round(absence_pct, 3),
                "Shift_Capacity": int(daily_capacity),
                "Planned_End_Backlog": int(planned_end_backlog),
                "Bridge_Action": action,
                "Action_Category": action_type,
                "Historical_Feedback": feedback
            }
            
            cascade_data.append(processed_shift)
            
            # Prepare row for CSV history
            log_entries.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Operating_Date": date_str,
                "Shift_Name": shift_name,
                "Volume": volume,
                "Action_Required": action,
                "Action_Category": trend_type,
                "End_Backlog_Risk": int(planned_end_backlog),
                "Historical_Feedback": feedback
            })
            
            rolling_backlog = planned_end_backlog

        # Persistent Logging
        df_new = pd.DataFrame(log_entries)
        header_needed = not os.path.exists(self.log_file)
        df_new.to_csv(self.log_file, mode='a', header=header_needed, index=False)

        return cascade_data