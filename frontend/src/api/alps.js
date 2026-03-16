import axios from 'axios';

// Ensure this matches the port where your FastAPI server is running
const API_URL = 'http://localhost:8000/api/alps';

export const predictFlow = async (shiftsData) => {
    try {
        const response = await axios.post(`${API_URL}/predict`, { shifts: shiftsData });
        return response.data.data;
    } catch (error) {
        console.error("ALPS API Integration Error:", error);
        throw error;
    }
};