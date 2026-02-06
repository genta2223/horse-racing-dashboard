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

def analyze_volume_zone():
    print("=== VOLUME ZONE ANALYSIS: The 'Bread and Butter' Hits ===")
    
    # 1. Load Data
    print(f"Loading data from {DATA_PATH}...")
    try:
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
    df['is_win'] = df['着順'].apply(lambda x: 1 if x <= 1 else 0)
    
    # 3. Load Model
    print(f"Loading model from {MODEL_PATH}...")
    try:
        model = joblib.load(MODEL_PATH)
    except Exception as e:
        print(f"Model load failed: {e}")
        return

    # 4. Predict
    print("Running Inference...")
    probs = model.predict_proba(df[features])[:, 1]
    df['ai_prob'] = probs
    
    if '単勝オッズ' not in df.columns:
        print("Error: Odds column missing.")
        return
        
    df['ev'] = df['ai_prob'] * df['単勝オッズ']
    
    # 5. Filter: EV > 1.34 (All Bets)
    all_bets = df[df['ev'] > 1.34].copy()
    # CSV might not have 'race_id', use 'Date' and maybe 'レース名' or just Date (Order in CSV is usually chrono)
    all_bets = all_bets.sort_values(['Date'])
    
    # hits only
    hits = all_bets[all_bets['is_win'] == 1].copy()
    
    print(f"\n[STATISTICS]")
    print(f"Total Bets: {len(all_bets)}")
    print(f"Total Hits: {len(hits)}")
    print(f"Hit Rate: {len(hits)/len(all_bets):.2%}")
    
    # 1. Statistics of Hits (Volume Zone)
    median_odds = hits['単勝オッズ'].median()
    mean_pop = hits['人気順'].mean()
    mean_prob = hits['ai_prob'].mean()
    mean_ev = hits['ev'].mean()
    
    print(f"\n## 1. Volume Zone Stats (Median/Mean of Hits)")
    print(f" - Median Winning Odds: {median_odds:.1f}")
    print(f" - Average Popularity: {mean_pop:.1f}th")
    print(f" - Average AI Probability: {mean_prob:.2%}")
    print(f" - Average EV: {mean_ev:.2f}")

    # 2. Typical Examples (Closest to Median Odds)
    print(f"\n## 2. Typical Examples (Closest to Median Odds: {median_odds})")
    hits['diff_from_median'] = abs(hits['単勝オッズ'] - median_odds)
    typical_hits = hits.sort_values('diff_from_median').head(3)
    
    importances = model.feature_importances_
    feat_imp_dict = dict(zip(features, importances))

    for idx, row in typical_hits.iterrows():
        print("-" * 60)
        date_str = row['Date'].strftime('%Y-%m-%d')
        print(f"Date: {date_str} | Race: {row.get('レース名', 'Unknown')}")
        print(f"Horse: {row['馬名']} (#{row['馬番']})")
        print(f"ODDS: {row['単勝オッズ']:.1f} (Pop: {row['人気順']})")
        print(f"AI Eval -> Prob: {row['ai_prob']:.2%} | EV: {row['ev']:.2f}")
        print(f"  [Why?] Key Feature Contributions:")
        print(f"    Prev_3F : {row.get('Prev_3F', '-')} (Imp: {feat_imp_dict.get('Prev_3F',0)})")
        print(f"    Prev_PCI: {row['Prev_PCI']:.1f} (Imp: {feat_imp_dict.get('Prev_PCI',0)})")
        print(f"    Prev_Rank: {row['Prev_Rank']} (Imp: {feat_imp_dict.get('Prev_Rank',0)})")


    # 3. Operational Simulation (Streaks)
    print(f"\n## 3. Operational Expectations (Simulation)")
    
    # Calculate streak of losses
    # We iterate through 'all_bets' in order
    current_loss_streak = 0
    max_loss_streak = 0
    loss_streaks = []
    
    hit_intervals = []
    last_hit_idx = -1
    
    # Reset index for iteration
    all_bets_sorted = all_bets.reset_index(drop=True)
    
    for idx, row in all_bets_sorted.iterrows():
        if row['is_win'] == 1:
            loss_streaks.append(current_loss_streak)
            if current_loss_streak > max_loss_streak:
                max_loss_streak = current_loss_streak
            current_loss_streak = 0
            
            if last_hit_idx != -1:
                hit_intervals.append(idx - last_hit_idx)
            last_hit_idx = idx
        else:
            current_loss_streak += 1
            
    # Include the final streak if it ended in loss
    loss_streaks.append(current_loss_streak)
    if current_loss_streak > max_loss_streak:
        max_loss_streak = current_loss_streak

    avg_loss_streak = np.mean(loss_streaks)
    avg_interval = np.mean(hit_intervals) if hit_intervals else 0
    
    print(f" - Max Consecutive Losses: {max_loss_streak}")
    print(f" - Avg Loss Streak: {avg_loss_streak:.1f}")
    print(f" - Avg Bets between Hits: {avg_interval:.1f}")
    print(f" - Conclusion: Be prepared to endure {max_loss_streak} losses in a worst-case scenario,")
    print(f"   but typically you win every {int(avg_interval)} bets.")

if __name__ == "__main__":
    analyze_volume_zone()
