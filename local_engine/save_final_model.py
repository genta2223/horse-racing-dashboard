import pandas as pd
import lightgbm as lgb
import joblib
import sys
import os
from preprocess import process_features

# Config
DATA_PATH = r"C:\TFJV\TXT\20210101-20251231-2.csv"
MODEL_PATH = r"final_model.pkl"

def train_and_save():
    print(f"Loading data from {DATA_PATH}...")
    try:
        df = pd.read_csv(DATA_PATH, encoding='cp932', low_memory=False)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    print("Preprocessing...")
    # Apply shared logic
    df, features = process_features(df)
    
    # Filter for Valid Training Rows (Must have history)
    df = df.dropna(subset=features + ['着順']) # '着順' is needed for target
    
    # Create Target
    # Note: '着順' was cleaned in process_features if it existed as '確定着順' mapping
    # But let's verify. process_features maps '着順' -> '確定着順' cleaned.
    # Actually process_features updates 'PCI', '上り3F', '着順' columns.
    df['target'] = df['着順'].apply(lambda x: 1 if x <= 1 else 0)

    # Train/Test Split logic from Simulation
    # Train on 2021-2024 (to reproduce the "Brain" that won in 2025)
    train_df = df[df['Date'].dt.year < 2025]
    print(f"Training Data: {len(train_df)} rows (2021-2024)")

    if train_df.empty:
        print("Error: No training data found.")
        return

    # Train Model
    print("Training LightGBM...")
    model = lgb.LGBMClassifier(
        n_estimators=100, 
        learning_rate=0.05, 
        num_leaves=31, 
        random_state=42
    )
    model.fit(train_df[features], train_df['target'])
    
    # Save
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")
    
    # Verify validity with a quick check
    print("Verifying model...")
    test_sample = train_df[features].head(1)
    pred = model.predict_proba(test_sample)
    print(f"Sample Prediction: {pred}")

if __name__ == "__main__":
    train_and_save()
