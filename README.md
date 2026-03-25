***

# ALPS Calc: Total Outbound Digital Twin

## 🚀 Overview
ALPS Calc is a full-stack, tactical shift simulator designed to bridge the gap between Amazon's static Central Flow plan (ALPS Basecamp) and the dynamic, minute-by-minute reality of the fulfillment center floor. 

Central planning tools generate shift plans days in advance, relying on historical averages that cannot react to live call-outs, late truck arrivals, or sudden sorter downtime. As a result, Area Managers and Flow Leads are often forced to make manual, "gut-feeling" labor adjustments (VTO/VET) during the shift, which frequently leads to the Bullwhip Effect—over-correcting and accidentally gridlocking or starving the subsequent shift.

I built this Digital Twin to solve that problem. By ingesting the ALPS Basecamp plan and applying live, localized variables—including a Machine Learning absence predictor and real-time building backlog—this tool allows the Flow Desk to securely simulate their labor levers *before* they pull them. It mathematically guarantees that shift transitions meet their exact Target Handoff Buffers (e.g., 15k+ units) to protect the building's CPU (Cost Per Unit) and ensure CPTs (Critical Pull Times) are met without relying on guesswork.

---

## 🧠 Machine Learning & AI "Triad" Integration

ALPS Calc goes beyond basic arithmetic by integrating predictive modeling and an experimental multi-agent AI environment to mirror real-world Flow Desk operations.

**1. ML Absence & Variance Predictor (`ml_predictor.py`)**
Basecamp assumes a static network average for shrinkage (e.g., 10%). ALPS Calc uses a localized Machine Learning model to predict actual shift variance. By analyzing historical site data, day-of-week trends, and scheduled headcount volumes, the ML engine overrides the static plan with a highly accurate predicted absence percentage. This ensures capacity planning is rooted in the building's actual behavioral trends, not a corporate average.

**2. The AI Council "War Room" (Experimental / In Development)**
Operations is a negotiation between departments (The Triad: Pick, Pack, and Dock). The `Live Flow Chime` tab in ALPS Calc introduces a simulated multi-agent LLM environment. Operating over an SQLite-backed IPC (Inter-Process Communication) bridge, this feature creates a simulated "War Room." When the math engine detects a massive deficit, you can dispatch a directive to the AI Council, and simulated Senior Leaders (Pick AM, Pack AM, Flow Desk) will debate the optimal Labor Share or VET strategy based on the math engine's output.

---

## 🛠️ How to Use the App (Flow Desk Workflow)

This tool is built for the "Waterfall Method" of labor planning, allowing you to solve the building chronologically.

1. **Prime the Pump:** Enter the **Current Starting Backlog** (live from FCLM/Rodeo) into the global settings. This injects the exact physical reality of the building into Shift 1.
2. **Input Basecamp Data:** Enter the planned Volume, Scheduled Headcount (HC), and Diluted TPH from ALPS Basecamp for the next 4–14 shifts. Ensure your **Target Buffer** is set to the network's required handoff volume (e.g., 15,000 for total OB, or 3,000 for local Pack WIP).
3. **Run the ALPS Math Engine:** Click the execute button to cascade the flow math. The ML engine will predict actual absence shrinkage, and the visualizer will instantly flag gridlocks (Surplus) or starvations (Deficits).
4. **Pull the Levers (The Triad Negotiation):** Look at the **Deficit / Surplus** column.
   * If a shift shows a `-160.0 Hr` deficit, enter `160` into **VET Net** (or **Misc Hrs** for Inbound labor sharing) to pull bodies in.
   * If a shift shows a `+200.0 Hr` surplus, enter `200` into **VTO Net** to save CPU.
5. **Re-Run & Balance:** Re-run the engine. The chart will flatline, the warnings will disappear, and every row will say **BALANCED**. You have now mathematically secured the building.

---

## 🧮 Core Flow Mathematics (ALPS Calculations)

The backend engine (`alps_service.py`) operates on the exact physics of Amazon flow, moving linearly through four phases to determine the operational health of the shift.

**1. Workable Demand:**
The total units a shift is responsible for managing.
$$W_{total} = V_{in} + B_{start}$$
*(Incoming Volume + Rolling Backlog from previous shift)*

**2. Net Shift Capacity (Show Hours & Volume):**
Calculates the exact units the floor can process, accounting for ML-predicted shrinkage and manual lever pulls.
$$H_{net} = (HC_{sched} \times (1 - \%_{abs}) + VET - VTO \pm LS) \times L_{shift}$$
$$C_{shift} = H_{net} \times TPH$$
*(HC = Headcount, LS = Labor Share, L = Shift Length, TPH = Diluted Throughput Per Hour)*

**3. Actionable Volume (WIP Protection):**
The building shouldn't process *all* volume; it must leave a safe buffer to prevent the next shift from starving.
$$V_{actionable} = \max(0, W_{total} - B_{target})$$
*(Actionable Volume = Workable Demand - Target Handoff Buffer)*

**4. The Executive Delta (Deficit/Surplus):**
The exact hour variance the Flow Desk needs to solve.
$$\Delta_{hours} = \frac{C_{shift} - V_{actionable}}{TPH}$$
* **Positive $\Delta$:** Shift has too much capacity (Surplus). Indicates a need to drop VTO or export Labor Share to prevent WIP blowout.
* **Negative $\Delta$:** Shift lacks capacity (Deficit). Indicates a need to call VET or import Labor Share to prevent CPT risk.

---

## 💻 Technical Stack & Libraries

### Backend (Python)
* **`FastAPI`**: A modern, high-performance web framework used to handle the API routing. Selected for its asynchronous capabilities, allowing rapid calculation loops without blocking the frontend.
* **`Pydantic`**: Used for strict data validation and typing. I implemented custom `@validator` decorators to automatically sanitize empty strings from the Vue frontend into safe `0.0` floats before they hit the math engine, preventing 500 server crashes.
* **`Pandas` & `Scikit-Learn`**: Utilized heavily in the `AlpsFlowEngine` and `ml_predictor.py` for complex DataFrame manipulation and predictive modeling. It handles historical trend analysis (detecting "Bullwhip" patterns) and manages the persistent logging.
* **`SQLite3`**: A lightweight, built-in database used to manage the IPC (Inter-Process Communication) and state for the live War Room/Chime simulation tab.

### Frontend (JavaScript / HTML / CSS)
* **`Vue.js 3` (Composition API)**: The core reactive framework. Uses `<script setup>` for clean, concise component logic. It manages the dynamic arrays for the shift input tables and provides seamless reactivity when adjusting VET/VTO levers.
* **`Axios`**: The HTTP client used to interface with the FastAPI backend and handle the payload transitions.
* **`Chart.js` & `vue-chartjs`**: Used to render the visual forecasting chart. It stacks the Capacity vs. End Backlog against the Target WIP limits, giving Senior OMs an immediate visual health check of the 2-week plan.

---

## 🏗️ Code Architecture & Core Functions

### 1. The Vue User Interface (`FlowDashboard.vue`)
* **`executeMathEngine()`**: Packages the live `initialBacklog` state and the `shiftInputs` array, bypassing local API wrappers to post directly to the backend. Updates the `results` array and reactively triggers the Chart.js re-render.
* **`processCsvUpload(file)`**: Intercepts drag-and-drop CSV files (Amazon Attendance/Roster exports), sends them to the backend for parsing, and populates the shift table automatically.
* **`pollChat() & sendMessage()`**: Manages the asynchronous polling and dispatching of commands to the SQLite-backed Chime simulator.
* **Dynamic CSS Bindings**: Implements real-time UX feedback, such as the `warning-bg` class that highlights rows in yellow if the scheduled headcount drops below 40, visually warning the Flow Lead that they are approaching a minimum "Skeleton Crew" threshold.

### 2. The API Router (`alps_router.py`)
* **`predict_flow(request: AlpsPredictionRequest)`**: The main operational endpoint. Extracts data using a robust "Dual-Key" mapping system to ensure absolute data transfer integrity between the Vue UI formats and the Math Engine requirements.
* **`parse_roster_csv(file: UploadFile)`**: A custom ingestion script that reads multi-table Amazon CSV exports. It hunts for the "Outbound" summary rows, calculates current on-premise attendance vs. scheduled, deduces real-time Absence or VET percentages, and constructs an ALPS-ready payload.
* **Simulation Endpoints**: Manages the API bridges (`/chat`, `/send`, `/simulations`) that allow the frontend to read from and write to the AI Council's active database state.

### 3. The Math Engine (`alps_service.py` & `ml_predictor.py`)
* **`AlpsFlowEngine.calculate_cascade(shift_data_list, initial_backlog)`**: The core brain of the application. 
    * **Loop Processing**: Iterates through each shift chronologically.
    * **Pump Priming**: Seeds the very first shift with the `initial_backlog` to anchor the math to the current physical state of the building.
    * **Machine Learning Injection**: Calls the ML engine to override static Basecamp shrinkage with localized, context-aware predictions.
    * **Historical Logging**: Appends every simulated action to a persistent CSV log, tracking the `Action_Category` to monitor for compounding management errors (e.g., VTOing 4 shifts in a row) and generates operational feedback warnings.
