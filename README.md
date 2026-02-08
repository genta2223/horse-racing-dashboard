# Horse Racing AI Dashboard

An automated investment system for JRA horse racing, powered by LightGBM and Streamlit.

## 🐎 System Components

### 1. Dashboard (`app.py`)
- **Type**: Streamlit App (Cloud)
- **Role**: Visualization & Command Center
- **Features**:
  - Real-time "Action Plan" (Buy signals)
  - Asset Simulation (Pattern A/B/C Risk Management)
  - Historical Backtesting

### 2. Local Engine (`local_engine/`)
The "Brain" of the system, running on your local Windows PC to bypass data restrictions.

- **`brain.py`**: 
  - Loads `final_model.pkl` to predict winning probabilities for new races.
  - Usage: `brain.predict(dataframe)`
- **`preprocess.py`**:
  - Converts raw JRA-VAN data into features (e.g., n-1 Shifted PCI, Late Speed).
- **`final_model.pkl`**:
  - LightGBM Model trained on 2021-2024 data.
  - Logic: Win Classification (EV > 1.34).

## 🚀 How to Run Predictions (Local)

1. **Setup Environment**:
   ```bash
   pip install pandas lightgbm joblib
   ```
2. **Execute Prediction**:
   (See `worker_collector.py` for full automation)
   ```python
   from local_engine.brain import Brain
   import pandas as pd
   
   # Load today's data (must include history for n-1 features)
   df = pd.read_csv("live_data.csv") 
   
   # Predict
   brain = Brain("local_engine/final_model.pkl")
   results = brain.predict(df)
   
   print(results)
   ```

## 📚 Documentation
- [System Requirements](docs/REQUIREMENTS.md)
- [System Specifications & Architecture](docs/SPECIFICATIONS.md)

## 🔄 Deployment
See `deploy_to_github.bat` for pushing updates.
