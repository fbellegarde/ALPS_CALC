Amazon ALPS Calc: Outbound Command CenterProject OverviewThe Amazon ALPS Digital Twin is a high-fidelity operational simulation and predictive engine designed for NACF (North American Customer Fulfillment) environments. It bridges the gap between raw logistics data and executive decision-making by combining a Cascading Math Engine, a Machine Learning Predictor, and an Autonomous AI Leadership Triad.Core Value PropositionWIP Protection: Real-time calculation of the 5,000-unit Target WIP Buffer.Predictive Staffing: ML-driven TPH and Absence forecasting.Conflict Resolution: AI agents (Sarah, Fernando, Alex, Marcus, David) simulate shift-floor negotiations via a secure IPC bridge.🏗️ System Architecture1. Backend (Python/FastAPI)The central nervous system of the project.AlpsFlowEngine: The core logic layer that calculates volume flow, labor requirements, and bridge actions (VTO/VET).ml_predictor.py: A variance engine that overrides static rates with ML-predicted TPH based on historical trends.alps_router.py: The API gateway providing endpoints for flow prediction, simulation discovery, and IPC message routing.2. Digital Twin Simulation (OASIS/SARA)The behavioral layer.Autonomous Agents: Five distinct Amazon Leadership personas with specific MBTI profiles and operational goals.Simulation Loop: A 72-hour autonomous cycle where agents "debate" shift plans based on math engine outputs.IPC Bridge: A JSON-based file signaling system that allows the Vue Frontend to inject live directives into the running simulation.3. Frontend (Vue 3/Vite)The executive dashboard.Flow Predictor: Interactive table for shift input and tactical bridge action generation.Cascade Forecast: Real-time visualization using Chart.js to map workable demand vs. capacity.Live Flow Chime: A "War Room" interface mimicking Amazon Chime for direct interaction with AI AMs/OMs.📂 Project StructurePlaintextalps_calc_mirofish/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI Routers (alps_router.py)
│   │   ├── services/       # Logic layer (alps_service.py, ml_predictor.py)
│   ├── scripts/            # Simulation runners (run_reddit_simulation.py)
│   ├── uploads/            # Simulation databases and IPC command folders
│   ├── .env                # API Keys for SARA Core
│   └── run_amazon_backend.py
├── frontend/
│   ├── src/
│   │   ├── views/          # Dashboard components (FlowDashboard.vue)
│   │   ├── api/            # Axios configurations
│   └── vite.config.js
└── README.md
🚀 Execution ProtocolStep 1: Initialize the Math BackendBashcd backend
python run_amazon_backend.py
Step 2: Launch the Digital TwinOpen a second terminal to initialize the AI Triad:Bashpython launch_flow_sim.py
# Copy the generated command and execute it to start the live simulation
Step 3: Start the Command Center UIBashcd frontend
npm run dev
🤖 The Leadership Triad (Personas)AgentRoleFocusMBTISarahSenior OM100k Ship Goal / CPU ProtectionENTJFernandoFlow LeadALPS Engine / Target WIP BufferINTJAlexPack AMAFE Wall Health / ConveyanceESTJMarcusPick AMHeadcount Retention / Faucet ControlISTJDavidDock AMTrans-out / Critical Pull Times (CPTs)ESTP📊 Technical CapabilitiesMathematical Models: Dynamic Handoff Calculation, True Show-Hour Analysis.Data Persistence: SQLite3 for simulation traces, CSV for historical shift logging.Real-time Communication: Non-blocking asynchronous input loops for live terminal/UI interaction.🛠️ Maintenance & Troubleshooting422 Errors: Ensure all numeric fields in the UI are filled; the Pydantic schema expects floats.IPC Command Failed: Verify that the uploads/simulations/{sim_id}/ipc_commands folder exists.SARA API Offline: Check the .env file for the correct OPENAI_API_BASE (localhost:8082).
