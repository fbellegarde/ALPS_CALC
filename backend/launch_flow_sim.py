import os
from app.services.simulation_manager import SimulationManager

def execute_launch():
    print("=========================================================")
    print(" 🚀 INITIALIZING AMAZON DIGITAL TWIN SIMULATION")
    print("=========================================================")
    
    manager = SimulationManager()
    
    # 1. Initialize a new digital twin environment
    state = manager.create_simulation(project_id="ALPS_FLOW_001", graph_id="LOCAL_DB")
    sim_id = state.simulation_id
    
    print(f"[*] Secure Environment Created: {sim_id}")
    print("[*] Injecting Amazon Leadership Personas...")
    
    # 2. Inject the Amazon Triad and ML guidelines
    manager.prepare_simulation(
        simulation_id=sim_id,
        simulation_requirement="Analyze the current ALPS Hours Delta. Flow Lead must declare Deficit or Surplus. Pick AM and Pack AM must debate labor sharing. Senior OM has final approval on VET.",
        document_text="Refer to the ALPS database for current shift parameters. Protect the Target WIP Buffer at all costs."
    )
    
    # 3. Retrieve the precise execution command
    instructions = manager.get_run_instructions(sim_id)
    launch_cmd = instructions["commands"]["chime"]
    
    print("\n✅ SIMULATION ENVIRONMENT PREPPED AND READY.")
    print("\nTo watch your AI Area Managers negotiate the Flow plan, copy and paste this exact command into your terminal:\n")
    print(f"    {launch_cmd}\n")
    print("=========================================================\n")

if __name__ == "__main__":
    execute_launch()