import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
import os

class AlpsMachineLearning:
    def __init__(self):
        self.model_path = "alps_tph_model.pkl"
        self.model = None

    def train_historical_model(self, historical_csv_path: str):
        """
        Trains the ML model on your building's past shifts to learn human variance.
        Expects a CSV with: DayOfWeek, Volume, SchedHC, ActualTPH, ActualAbsence
        """
        print("[*] Training ALPS Machine Learning Engine...")
        df = pd.read_csv(historical_csv_path)
        
        # Convert Day of Week (Mon, Tue) to numerical values for the AI
        df['DayOfWeek_Num'] = pd.Categorical(df['DayOfWeek']).codes

        # Features (What we know before the shift starts)
        X = df[['DayOfWeek_Num', 'Volume', 'SchedHC']]
        
        # Targets (What we are trying to predict)
        # We predict both TPH and Absence % simultaneously
        y = df[['ActualTPH', 'ActualAbsence']]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Random Forest Regressor handles complex, non-linear human behaviors perfectly
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Save the brain to the hard drive
        joblib.dump(self.model, self.model_path)
        
        score = self.model.score(X_test, y_test)
        print(f"[+] AI Training Complete. Model Accuracy Score: {score:.2f}")

    def predict_shift_variance(self, day_of_week: str, volume: float, sched_hc: float):
        """
        Uses the trained AI to predict the actual TPH and Absence % for an upcoming shift.
        """
        if not os.path.exists(self.model_path):
            # Fallback to standard ALPS metrics if the AI hasn't been trained yet
            return {"Predicted_TPH": 14.6, "Predicted_Absence": 0.10}

        self.model = joblib.load(self.model_path)
        
        day_mapping = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
        day_num = day_mapping.get(day_of_week[:3], 0)

        # Predict using the input features
        prediction = self.model.predict([[day_num, volume, sched_hc]])
        
        return {
            "Predicted_TPH": round(prediction[0][0], 2),
            "Predicted_Absence": round(prediction[0][1], 2)
        }