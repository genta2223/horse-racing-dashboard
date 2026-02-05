import pandas as pd
import joblib
import os
import sys
from .preprocess import process_features

class Brain:
    def __init__(self, model_path="final_model.pkl"):
        # Resolve path relative to this script if not absolute
        if not os.path.isabs(model_path):
            model_path = os.path.join(os.path.dirname(__file__), model_path)
            
        print(f"[BRAIN] Loading Model from {model_path}...")
        try:
            self.model = joblib.load(model_path)
            print("[BRAIN] Model Loaded Successfully.")
        except Exception as e:
            print(f"[BRAIN] Failed to load model: {e}")
            self.model = None

    def predict(self, df):
        """
        Takes a raw dataframe (formatted like TARGET CSV),
        applies preprocessing, and returns predictions.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded.")

        # Preprocess
        df_processed, features = process_features(df)
        
        # We need historical data for 'Shift' to work.
        # If 'df' only contains TODAY's race, shift(1) will produce NaN.
        # The calling script (Worker) must provide concatenated history 
        # OR we need a dedicated 'fetch_history' mechanism inside preprocess.
        # For now, we assume 'df' includes necessary history or pre-calculated lag features.
        
        # Check for missing columns
        missing = [c for c in features if c not in df_processed.columns]
        if missing:
            # If Lag features are missing (NaN), we cannot predict.
            # But process_features calculates them. If they are NaN, it means not enough history.
            pass

        # Filter rows valid for prediction (must have features)
        # We perform prediction on ALL rows that have valid features.
        valid_mask = df_processed[features].notna().all(axis=1)
        valid_df = df_processed[valid_mask].copy()
        
        if valid_df.empty:
            print("[BRAIN] No valid rows for prediction (History missing?).")
            return pd.DataFrame()

        # Predict
        probs = self.model.predict_proba(valid_df[features])[:, 1]
        valid_df['ai_prob'] = probs
        
        # EV Check (if Odds available)
        if '単勝オッズ' in valid_df.columns:
            valid_df['ev'] = valid_df['ai_prob'] * valid_df['単勝オッズ']
        
        return valid_df[['Date', 'race_id', '馬番', 'ai_prob', 'ev'] if 'race_id' in valid_df.columns else ['Date', '馬番', 'ai_prob', 'ev']]

if __name__ == "__main__":
    # Test Run
    brain = Brain()
    # Dummy load for test if needed...
