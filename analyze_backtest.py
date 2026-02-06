import pandas as pd
import lightgbm as lgb
import joblib
import sys
import os
import numpy as np

# Add local path
sys.path.append(os.getcwd())

from local_engine.preprocess import process_features

MODEL_PATH = r"C:\TFJV\my-racing-dashboard\local_engine\final_model.pkl"
DATA_PATH = r"C:\TFJV\TXT\20210101-20251231-2.csv"

def analyze_history():
    print("=== BACKTEST ANALYSIS: High Dividend Hits (EV > 1.34) ===")
    
    # 1. Load Data
    print(f"Loading data from {DATA_PATH}...")
    try:
        # encoding cp932 is standard for JRA-VAN CSVs
        df = pd.read_csv(DATA_PATH, encoding='cp932', low_memory=False)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    # 2. Preprocess
    print("Preprocessing...")
    df, features = process_features(df)
    
    # Drop rows without targets or features
    df = df.dropna(subset=features + ['着順'])
    
    # Target Construction (Win = 1)
    # Note: '着順' is raw rank.
    df['is_win'] = df['着順'].apply(lambda x: 1 if x <= 1 else 0)
    
    # 3. Load Model
    print(f"Loading model from {MODEL_PATH}...")
    try:
        model = joblib.load(MODEL_PATH)
    except Exception as e:
        print(f"Model load failed: {e}")
        return

    # 4. Predict (Re-running history to see what the Current Brain WOULD have done)
    print("Running Inference on History (2021-2025)...")
    # This might take a moment for 5 years
    probs = model.predict_proba(df[features])[:, 1]
    df['ai_prob'] = probs
    
    # Calculate EV
    # Assuming '単勝オッズ' exists (cleaned by preprocess)
    if '単勝オッズ' not in df.columns:
        print("Error: Odds column missing.")
        return
        
    df['ev'] = df['ai_prob'] * df['単勝オッズ']
    
    # 5. Filter: EV > 1.34 AND Result = WIN
    print("Filtering High EV Winners...")
    high_ev_winners = df[
        (df['ev'] > 1.34) & 
        (df['is_win'] == 1)
    ].copy()
    
    print(f"Found {len(high_ev_winners)} wins meeting criteria out of {len(df)} rows.")
    
    # 6. Sort by Odds (Dividends) Descending
    top_hits = high_ev_winners.sort_values('単勝オッズ', ascending=False).head(10)
    
    # 7. Report and Analyze
    print("\n[TOP 10 HIGH DIVIDEND HITS (Simulated with Current Logic)]")
    
    # Global Feature Importance for context
    importances = model.feature_importances_
    feat_imp_dict = dict(zip(features, importances))
    
    for idx, row in top_hits.iterrows():
        print("="*60)
        date_str = row['Date'].strftime('%Y-%m-%d')
        print(f"Date: {date_str} | Race: {row.get('レース名', 'Unknown')} | Grade: {row.get('グレード', '-')}")
        print(f"Horse: {row['馬名']} (#{row['馬番']})")
        print(f"ODDS: {row['単勝オッズ']:.1f} (Pop: {row['人気順']})")
        print(f"AI Eval -> Prob: {row['ai_prob']:.2%} | EV: {row['ev']:.2f}")
        
        # Why did valid? Feature Contribution (Simplified)
        # We look at features that contributed positively relative to mean?
        # Or just show key stats.
        print("  [Key Factors]")
        print(f"    Prev_3F : {row.get('Prev_3F', '-')} (Imp: {feat_imp_dict.get('Prev_3F',0)})")
        print(f"    Prev_PCI: {row['Prev_PCI']:.1f} (Imp: {feat_imp_dict.get('Prev_PCI',0)})")
        print(f"    Prev_Rank: {row['Prev_Rank']} (Imp: {feat_imp_dict.get('Prev_Rank',0)})")
        
        # Brief "Gap" Analysis
        print("  [Analysis]")
        if row['ai_prob'] > 0.10: # >10% win rate assigned to a longshot
             print("    Logic detected HIGH win probability (>10%) despite high odds.")
             print("    Likely due to strong underlying metrics (PCI/3F) ignored by public.")
        else:
             print("    Logic saw moderate chance, but Odds were MASSIVE, pushing EV > 1.34.")
             print("    Example of 'Value Betting' on volatility.")

if __name__ == "__main__":
    analyze_history()
