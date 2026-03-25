<template>
  <div class="alps-dashboard">
    <header class="dashboard-header">
      <h1>AMAZON Flow Command Center</h1>
      <p>Outbound ALPS Calculator (Powered by Machine Learning)</p>
      
      <div class="tab-menu">
        <button :class="{ active: activeTab === 'predictor' }" @click="activeTab = 'predictor'">📊 Flow Predictor</button>
        <button :class="{ active: activeTab === 'chime' }" @click="openChime">💬 Live Flow Chime</button>
      </div>
    </header>

    <div v-if="activeTab === 'predictor'">
      <div class="control-panel">
        <h2>1. Shift Input Data</h2>

        <div 
          class="csv-drop-zone" 
          @dragover.prevent="isDragging = true" 
          @dragleave.prevent="isDragging = false" 
          @drop.prevent="handleDrop"
          :class="{ 'dragging': isDragging }"
        >
          <div v-if="uploadingCsv" class="upload-spinner">Parsing Data...</div>
          <div v-else>
            <span class="drop-icon">📁</span>
            <p>Drag & Drop Amazon Roster CSV Here</p>
            <p class="sub-text">or click to browse</p>
            <input type="file" accept=".csv" class="file-input" @change="handleFileSelect" />
          </div>
        </div>

        <div class="global-settings">
          <strong>Live Building Variables:</strong>
          <label>Current Starting Backlog:</label>
          <input type="number" v-model.number="initialBacklog" placeholder="e.g. 19500" class="backlog-input" />
          <span class="sub-text">(Injected into Shift 1 calculations)</span>
        </div>

        <button class="btn-amazon" @click="addShift">➕ Add Shift</button>
        <div class="table-container">
          <table class="input-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Shift</th>
                <th>Volume</th>
                <th>Target Buffer</th>
                <th>TPH</th>
                <th>Sched HC</th>
                <th>Absence %</th>
                <th>VET Net</th>
                <th>VTO Net</th>
                <th>Misc Hrs</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(shift, index) in shiftInputs" :key="index">
                <td><input type="text" v-model="shift.Date" /></td>
                <td>
                  <select v-model="shift.Shift">
                    <option>Day</option>
                    <option>Night</option>
                  </select>
                </td>
                <td><input type="number" v-model.number="shift.Volume" /></td>
                <td><input type="number" v-model.number="shift.Target_Handoff_Buffer" step="100" style="width: 80px;" /></td>
                <td><input type="number" v-model.number="shift.Diluted_Rate_TPH" step="0.1" style="width: 70px;" /></td>
                <td :class="{ 'warning-bg': shift.Scheduled_HC > 0 && shift.Scheduled_HC < 40 }">
                  <input type="number" v-model.number="shift.Scheduled_HC" />
                </td>
                <td><input type="number" v-model.number="shift.Absence_Pct" step="0.01" /></td>
                <td><input type="number" v-model.number="shift.VET_Net_Hrs" /></td>
                <td><input type="number" v-model.number="shift.VTO_Net_Hrs" /></td>
                <td><input type="number" v-model.number="shift.Misc_Labor_Share_Hrs" /></td>
                <td><button class="btn-danger" @click="removeShift(index)">X</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <button class="btn-amazon-primary" @click="executeMathEngine" :disabled="loading">
          {{ loading ? 'Processing Flow & Consulting ML Engine...' : '🚀 Run ALPS Math Engine' }}
        </button>
      </div>

      <div v-if="results.length > 0" class="results-panel">
        <h2>2. Visual Forecast</h2>
        <div class="chart-container">
          <Chart type="bar" :data="chartData" :options="chartOptions" />
        </div>

        <h2>3. Tactical Actions</h2>
        <div class="table-container">
          <table class="output-table">
            <thead>
              <tr>
                <th>Date (Shift)</th>
                <th>Workable Demand</th>
                <th>Target Buffer</th>
                <th> ML TPH</th>
                <th> ML Absence</th>
                <th>Capacity</th>
                <th>End Backlog</th>
                <th>Deficit / Surplus</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(res, index) in results" :key="index">
                <td>{{ res.Date }} ({{ res.Shift }})</td>
                <td>{{ res.Total_Workable_Demand.toLocaleString() }}</td>
                <td class="text-teal">{{ res.Target_Buffer.toLocaleString() }}</td>
                <td class="text-ai">{{ res.AI_Predicted_TPH || '14.60' }}</td>
                <td class="text-ai">{{ res.AI_Predicted_Absence ? (res.AI_Predicted_Absence * 100).toFixed(1) : '10.0' }}%</td>
                <td>{{ res.Shift_Capacity.toLocaleString() }}</td>
                <td class="text-red">{{ res.Planned_End_Backlog.toLocaleString() }}</td>
                <td :class="res.Action_Category === 'VTO' ? 'text-green' : 'text-red'">
                  <strong>{{ res.Bridge_Action }}</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'chime'" class="chime-container">
      <div class="chime-sidebar">
        <h3>War Rooms</h3>
        <button class="btn-amazon" @click="fetchSimulations">🔄 Refresh</button>
        <ul>
          <li v-for="sim in simulationsList" :key="sim.simulation_id" 
              :class="{ active: selectedSimId === sim.simulation_id }"
              @click="selectSimulation(sim.simulation_id)">
            NACF-OPS-{{ sim.simulation_id.substring(4, 10).toUpperCase() }}
          </li>
        </ul>
      </div>
      <div class="chime-window">
        <div class="chime-header">
          <strong># NACF-Flow-Coordination</strong>
          <span v-if="selectedSimId" class="status-pill">SECURE-LINE: {{ selectedSimId.substring(4,12) }}</span>
        </div>
        <div class="chime-messages" ref="messageContainer">
          <div v-for="(msg, idx) in chatLogs" :key="idx" class="chime-msg">
            <span class="msg-author">{{ getAgentName(msg.agent_id) }}</span>
            <span class="msg-time">{{ formatTime(msg.time) }}</span>
            <p class="msg-content">{{ msg.message }}</p>
          </div>
          <div v-if="chatLogs.length === 0" class="chime-empty">Select a war room to view the ALPS Triad negotiation.</div>
        </div>
        <div class="chime-input-bar">
          <input type="text" v-model="newMessage" placeholder="Direct order to Leadership Team..." @keyup.enter="sendMessage" :disabled="!selectedSimId" />
          <button class="btn-send" @click="sendMessage" :disabled="!selectedSimId || !newMessage">SEND</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, LineController, BarController } from 'chart.js';
import { Chart } from 'vue-chartjs';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, LineController, BarController);

// API Configuration
const API_BASE = 'http://localhost:8000/api/alps';

// Preserved Original State
const loading = ref(false);
const results = ref([]);
const initialBacklog = ref(0); // ENHANCEMENT: Master state for initial pump prime
const shiftInputs = ref([
  // === WEEK 1: STANDARD FLOW ===
  { Date: '2026-03-01', Shift: 'Day', Volume: 28000, Scheduled_HC: 210, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-01', Shift: 'Night', Volume: 29000, Scheduled_HC: 215, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-02', Shift: 'Day', Volume: 34000, Scheduled_HC: 240, Absence_Pct: 0.08, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-02', Shift: 'Night', Volume: 35000, Scheduled_HC: 245, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-03', Shift: 'Day', Volume: 33000, Scheduled_HC: 235, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-03', Shift: 'Night', Volume: 34000, Scheduled_HC: 240, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-04', Shift: 'Day', Volume: 32000, Scheduled_HC: 230, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-04', Shift: 'Night', Volume: 33000, Scheduled_HC: 235, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-05', Shift: 'Day', Volume: 31000, Scheduled_HC: 230, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-05', Shift: 'Night', Volume: 32000, Scheduled_HC: 235, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-06', Shift: 'Day', Volume: 30000, Scheduled_HC: 220, Absence_Pct: 0.13, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-06', Shift: 'Night', Volume: 31000, Scheduled_HC: 225, Absence_Pct: 0.14, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-07', Shift: 'Day', Volume: 28000, Scheduled_HC: 210, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-07', Shift: 'Night', Volume: 29000, Scheduled_HC: 215, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },

  // === WEEK 2: THE "PRIME" PUSH (Massive Volume, Causes Deficits) ===
  { Date: '2026-03-08', Shift: 'Day', Volume: 38000, Scheduled_HC: 230, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-08', Shift: 'Night', Volume: 40000, Scheduled_HC: 240, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-09', Shift: 'Day', Volume: 45000, Scheduled_HC: 250, Absence_Pct: 0.08, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-09', Shift: 'Night', Volume: 46000, Scheduled_HC: 255, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-10', Shift: 'Day', Volume: 44000, Scheduled_HC: 250, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-10', Shift: 'Night', Volume: 45000, Scheduled_HC: 255, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-11', Shift: 'Day', Volume: 43000, Scheduled_HC: 245, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-11', Shift: 'Night', Volume: 44000, Scheduled_HC: 250, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-12', Shift: 'Day', Volume: 42000, Scheduled_HC: 240, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-12', Shift: 'Night', Volume: 43000, Scheduled_HC: 245, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-13', Shift: 'Day', Volume: 40000, Scheduled_HC: 235, Absence_Pct: 0.13, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-13', Shift: 'Night', Volume: 41000, Scheduled_HC: 240, Absence_Pct: 0.14, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-14', Shift: 'Day', Volume: 38000, Scheduled_HC: 230, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-14', Shift: 'Night', Volume: 39000, Scheduled_HC: 235, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },

  // === WEEK 3: POST-PEAK CRASH (Volume drops, Causes VTO needs) ===
  { Date: '2026-03-15', Shift: 'Day', Volume: 24000, Scheduled_HC: 230, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-15', Shift: 'Night', Volume: 25000, Scheduled_HC: 235, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-16', Shift: 'Day', Volume: 26000, Scheduled_HC: 230, Absence_Pct: 0.08, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-16', Shift: 'Night', Volume: 27000, Scheduled_HC: 235, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-17', Shift: 'Day', Volume: 25000, Scheduled_HC: 220, Absence_Pct: 0.09, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-17', Shift: 'Night', Volume: 26000, Scheduled_HC: 225, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-18', Shift: 'Day', Volume: 24000, Scheduled_HC: 215, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-18', Shift: 'Night', Volume: 25000, Scheduled_HC: 220, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-19', Shift: 'Day', Volume: 23000, Scheduled_HC: 210, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-19', Shift: 'Night', Volume: 24000, Scheduled_HC: 215, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-20', Shift: 'Day', Volume: 22000, Scheduled_HC: 200, Absence_Pct: 0.13, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-20', Shift: 'Night', Volume: 23000, Scheduled_HC: 210, Absence_Pct: 0.14, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-21', Shift: 'Day', Volume: 20000, Scheduled_HC: 190, Absence_Pct: 0.12, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 },
  { Date: '2026-03-21', Shift: 'Night', Volume: 21000, Scheduled_HC: 195, Absence_Pct: 0.11, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 }
]);

// New Integrated State
const activeTab = ref('predictor');
const simulationsList = ref([]);
const selectedSimId = ref(null);
const chatLogs = ref([]);
const newMessage = ref("");
const messageContainer = ref(null);

// ENHANCEMENT: CSV Upload State
const isDragging = ref(false);
const uploadingCsv = ref(false);

// ENHANCEMENT: CSV Upload Methods
const handleDrop = async (event) => {
  isDragging.value = false;
  const files = event.dataTransfer.files;
  if (files.length > 0) {
    await processCsvUpload(files[0]);
  }
};

const handleFileSelect = async (event) => {
  const files = event.target.files;
  if (files.length > 0) {
    await processCsvUpload(files[0]);
  }
};

const processCsvUpload = async (file) => {
  if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
    alert('Strictly CSV files are supported.');
    return;
  }

  uploadingCsv.value = true;
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await axios.post(`${API_BASE}/upload_roster`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    if (response.data.status === 'success') {
      shiftInputs.value = response.data.data;
    }
  } catch (error) {
    console.error('CSV Upload Error:', error);
    alert('Failed to parse CSV. Check backend logs.');
  } finally {
    uploadingCsv.value = false;
    const fileInput = document.querySelector('.file-input');
    if (fileInput) fileInput.value = '';
  }
};

// Preserved Original Methods
const addShift = () => {
  shiftInputs.value.push({ Date: '2026-MM-DD', Shift: 'Day', Volume: 0, Scheduled_HC: 0, Absence_Pct: 0.10, VET_Net_Hrs: 0, VTO_Net_Hrs: 0, Misc_Labor_Share_Hrs: 0, Target_Handoff_Buffer: 3000, Diluted_Rate_TPH: 14.6, Shift_Length_Hrs: 10.0 });
};

const removeShift = (index) => {
  shiftInputs.value.splice(index, 1);
};

// ENHANCEMENT: Bypass local API wrapper to directly pass the new payload
const executeMathEngine = async () => {
  loading.value = true;
  try {
    const response = await axios.post(`${API_BASE}/predict`, {
      initial_backlog: initialBacklog.value,
      shifts: shiftInputs.value
    });
    results.value = response.data.data;
  } catch (error) {
    console.error("API Error Details:", error);
    alert("API Error: Backend Port 8000 Offline");
  } finally {
    loading.value = false;
  }
};

// New Simulation Methods
const openChime = () => { activeTab.value = 'chime'; fetchSimulations(); };

const fetchSimulations = async () => {
  try {
    const res = await axios.get(`${API_BASE}/simulations?t=${new Date().getTime()}`);
    simulationsList.value = res.data;
  } catch (e) { console.error("Sim fetch failed"); }
};

const selectSimulation = (id) => {
  selectedSimId.value = id;
  pollChat();
};

const sendMessage = async () => {
  if (!newMessage.value || !selectedSimId.value) return;
  const text = newMessage.value;
  newMessage.value = ""; // Clear for UI responsiveness
  
  try {
    const response = await axios.post(`${API_BASE}/simulation/${selectedSimId.value}/send`, 
      { message: text },
      { headers: { 'Content-Type': 'application/json' } }
    );
    
    if (response.data.status === "success") {
      console.log("Directive sent to ALPS Triad");
      setTimeout(pollChat, 1500); // Wait for SARA to process the debate
    } else {
      alert("Bridge Error: " + response.data.message);
    }
  } catch (e) {
    console.error("IPC Error Details:", e.response?.data || e.message);
    alert("IPC Command Failed. Check if Backend is still running on port 8000.");
  }
};

const pollChat = async () => {
  if (!selectedSimId.value || activeTab.value !== 'chime') return;
  try {
    const res = await axios.get(`${API_BASE}/simulation/${selectedSimId.value}/chat`);
    chatLogs.value = res.data.data.reverse();
    setTimeout(() => { if (messageContainer.value) messageContainer.value.scrollTop = messageContainer.value.scrollHeight; }, 50);
  } catch (e) {}
};

const getAgentName = (id) => ["Sarah (SR OM)", "Fernando (Flow)", "Alex (Pack)", "Marcus (Pick)", "David (Dock)"][id] || `User ${id}`;
const formatTime = (ts) => ts ? ts.split('T')[1]?.substring(0, 5) : '--:--';

// Preserved Chart Computation
const chartData = computed(() => {
  if (!results.value.length) return { labels: [], datasets: [] };
  return {
    labels: results.value.map(r => `${r.Date} ${r.Shift}`),
    datasets: [
      { type: 'line', label: 'Workable Demand', data: results.value.map(r => r.Total_Workable_Demand), borderColor: '#FF9900', borderWidth: 3, tension: 0.1 },
      { type: 'line', label: 'Target WIP Buffer', data: results.value.map(r => r.Target_Buffer), borderColor: '#008296', borderDash: [5, 5], borderWidth: 2, tension: 0 },
      { type: 'bar', label: 'Shift Capacity', data: results.value.map(r => r.Shift_Capacity), backgroundColor: '#232F3E' },
      { type: 'bar', label: 'End Backlog', data: results.value.map(r => r.Planned_End_Backlog), backgroundColor: '#D13212' }
    ]
  };
});

const chartOptions = { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Units' } } } };

onMounted(() => {
  fetchSimulations(); // Populate sidebar on load
  setInterval(() => { if (activeTab.value === 'chime') pollChat(); }, 3000);
});
</script>

<style scoped>
/* PRESERVED ORIGINAL STYLES */
.alps-dashboard { padding: 20px; font-family: 'Segoe UI', sans-serif; background-color: #f4f4f4; min-height: 100vh; }
.dashboard-header { background-color: #232F3E; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.dashboard-header h1 { margin: 0; color: #FF9900; }
.control-panel, .results-panel { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.table-container { overflow-x: auto; margin-bottom: 15px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
th { background-color: #232F3E; color: white; }
input, select { width: 90%; padding: 4px; box-sizing: border-box; }
.chart-container { position: relative; height: 400px; width: 100%; margin-bottom: 20px; }
.btn-amazon { background-color: #eaeded; border: 1px solid #a6a6a6; padding: 6px 12px; cursor: pointer; border-radius: 4px; color: #111; margin-bottom: 10px;}
.btn-amazon-primary { background-color: #FF9900; border: 1px solid #a88734; padding: 10px 20px; cursor: pointer; border-radius: 4px; color: #111; font-weight: bold; font-size: 16px; width: 100%; }
.btn-danger { background-color: #D13212; color: white; border: none; padding: 4px 8px; cursor: pointer; border-radius: 4px; }
.text-teal { color: #008296; font-weight: bold; }
.text-red { color: #D13212; font-weight: bold; }
.text-green { color: #006100; font-weight: bold; }
.text-ai { color: #8a2be2; font-weight: bold; }

/* ENHANCEMENT: Skeleton Crew Warning */
.warning-bg { background-color: #fff4e5; border: 2px solid #FF9900; }

/* ENHANCEMENT: Global Settings Input */
.global-settings { background: #fff4e5; border-left: 5px solid #FF9900; padding: 15px; margin-bottom: 20px; border-radius: 4px; }
.global-settings strong { color: #232F3E; margin-right: 15px; }
.global-settings label { font-weight: bold; margin-right: 10px; }
.backlog-input { width: 150px; padding: 6px; border: 1px solid #ccc; border-radius: 4px; display: inline-block; }

/* ENHANCEMENT: CSV DRAG & DROP ZONE STYLES */
.csv-drop-zone { border: 2px dashed #a6a6a6; border-radius: 8px; background-color: #f8f8f8; text-align: center; padding: 30px 20px; margin-bottom: 20px; position: relative; transition: all 0.2s ease-in-out; cursor: pointer; }
.csv-drop-zone.dragging { border-color: #FF9900; background-color: #fff4e5; }
.csv-drop-zone p { margin: 5px 0; color: #232F3E; font-weight: bold; }
.csv-drop-zone .sub-text { font-size: 12px; color: #555; font-weight: normal; }
.drop-icon { font-size: 32px; display: block; margin-bottom: 10px; }
.file-input { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.upload-spinner { color: #008296; font-weight: bold; animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }

/* NEW TAB & CHIME STYLES */
.tab-menu { margin-top: 15px; display: flex; gap: 10px; }
.tab-menu button { background: rgba(255,255,255,0.1); border: 1px solid #555; color: white; padding: 8px 15px; cursor: pointer; border-radius: 4px; }
.tab-menu button.active { background: #FF9900; color: #232F3E; border-color: #FF9900; font-weight: bold; }

.chime-container { display: flex; height: 600px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
.chime-sidebar { width: 220px; background: #eaeded; border-right: 1px solid #ddd; padding: 15px; }
.chime-sidebar ul { list-style: none; padding: 0; margin-top: 10px; }
.chime-sidebar li { padding: 10px; margin-bottom: 5px; background: white; cursor: pointer; border-radius: 4px; font-size: 12px; border: 1px solid #ccc; }
.chime-sidebar li.active { border-left: 5px solid #FF9900; background: #fff4e5; font-weight: bold; }
.chime-window { flex-grow: 1; display: flex; flex-direction: column; }
.chime-header { padding: 15px; border-bottom: 1px solid #ddd; background: #f8f8f8; display: flex; justify-content: space-between; }
.status-pill { background: #008296; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.chime-messages { flex-grow: 1; padding: 20px; overflow-y: auto; background: #fff; }
.chime-msg { margin-bottom: 15px; }
.msg-author { font-weight: bold; color: #007eb9; font-size: 14px; margin-right: 10px; }
.msg-time { font-size: 10px; color: #999; }
.msg-content { margin: 5px 0 0 0; background: #f1f1f1; padding: 10px 15px; border-radius: 12px; display: inline-block; max-width: 80%; line-height: 1.4; }
.chime-input-bar { padding: 15px; border-top: 1px solid #ddd; display: flex; gap: 10px; }
.chime-input-bar input { flex-grow: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
.btn-send { background: #FF9900; color: #232F3E; border: none; padding: 0 25px; border-radius: 4px; font-weight: bold; cursor: pointer; }
</style>