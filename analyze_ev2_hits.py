import pandas as pd
import joblib
import sys
import os
import numpy as np

# Add local path
sys.path.append(os.getcwd())

from local_engine.preprocess import process_features

MODEL_PATH = r"C:\TFJV\my-racing-dashboard\local_engine\final_model.pkl"
DATA_PATH = r"C:\TFJV\TXT\20210101-20251231-2.csv"

def analyze_ev2():
    print("=== HYBRID EV 2.0: Historical Analysis (2021-2024) ===")
    
    # 1. Load & Preprocess
    print("Loading Data...")
    try:
        df = pd.read_csv(DATA_PATH, encoding='cp932', low_memory=False)
        df, features = process_features(df)
        df = df.dropna(subset=features + ['着順'])
        df['is_win'] = df['着順'].apply(lambda x: 1 if x <= 1 else 0)
        
        # Load Model & Predict
        model = joblib.load(MODEL_PATH)
        df['ai_prob'] = model.predict_proba(df[features])[:, 1]
        df['ev'] = df['ai_prob'] * df['単勝オッズ']
        
    except Exception as e:
        print(f"Error: {e}")
        return

    # 2. Filter: EV > 2.0 AND (30.0 <= Odds <= 100.0)
    print("Filtering for EV > 2.0 and Odds 30x - 100x...")
    
    target_hits = df[
        (df['ev'] > 2.0) & 
        (df['is_win'] == 1) &
        (df['単勝オッズ'] >= 30.0) &
        (df['単勝オッズ'] <= 100.0)
    ].copy()
    
    target_misses = df[
        (df['ev'] > 2.0) & 
        (df['is_win'] == 0) & # Lost
        (df['着順'] > 5) & # Clear loss
        (df['単勝オッズ'] >= 30.0) &
        (df['単勝オッズ'] <= 100.0)
    ].copy()

    # Sort hits by Date (Recent first)
    target_hits = target_hits.sort_values('Date', ascending=False)
    
    # Feature Importance to explain "Why"
    importances = model.feature_importances_
    feat_imp_dict = dict(zip(features, importances))
    
    # 3. Report Hits (Top 10)
    print(f"\n[FOUND {len(target_hits)} HITS in the Volume Zone (30-100x, EV>2.0)]")
    
    for idx, row in target_hits.head(10).iterrows():
        print("="*60)
        date_str = row['Date'].strftime('%Y-%m-%d')
        print(f"Date: {date_str} | Race: {row.get('レース名', 'Unknown')}")
        print(f"Horse: {row['馬名']} (#{row['馬番']})")
        print(f"ODDS: {row['単勝オッズ']:.1f} (Pop: {row['人気順']})")
        print(f"METRICS -> Prob: {row['ai_prob']:.2%} | EV: {row['ev']:.2f}")
        
        # Key Features Analysis
        print("  [Logic Dissection]")
        print(f"    Prev_PCI: {row['Prev_PCI']:.1f}  (Avg Pace Change)")
        print(f"    Prev_3F : {row['Prev_3F']:.1f}  (Late Speed)")
        print(f"    Prev_Rank: {row['Prev_Rank']}   (Class Check)")
        
        # Simple Interpretation
        if row['Prev_PCI'] > 55:
            print("    -> HIGH PCI detected: Horse has exceptional gear-change ability masked by recent results.")
        if row['Prev_Rank'] > 5 and row['ai_prob'] > 0.05:
            print("    -> RECOVERY Signal: AI ignored poor previous rank, focusing on time indices.")

    # 4. Report Misses (Top 2)
    print(f"\n[ANALYSIS OF MISSES (EV > 2.0 but Lost)]")
    for idx, row in target_misses.sort_values('ev', ascending=False).head(2).iterrows():
        print("-" * 60)
        date_str = row['Date'].strftime('%Y-%m-%d')
        print(f"Date: {date_str} | Race: {row.get('レース名', 'Unknown')}")
        print(f"Horse: {row['馬名']} (Rank: {row['着順']})")
        print(f"ODDS: {row['単勝オッズ']:.1f} | Prob: {row['ai_prob']:.2%} | EV: {row['ev']:.2f}")
        print("  [Potential Cause]")
        print(f"    High expectation based on PCI {row['Prev_PCI']:.1f} and 3F {row['Prev_3F']:.1f}.")
        print("    Likely external factors (Track bias, Bad Start, Blocked) or Overfitting on specific past race.")

if __name__ == "__main__":
    analyze_ev2()
