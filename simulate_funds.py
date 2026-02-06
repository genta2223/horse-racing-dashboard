import pandas as pd
import numpy as np
import joblib
import sys
import os
# import matplotlib.pyplot as plt # Skipped

# Add local path
sys.path.append(os.getcwd())

from local_engine.preprocess import process_features

MODEL_PATH = r"C:\TFJV\my-racing-dashboard\local_engine\final_model.pkl"
DATA_PATH = r"C:\TFJV\TXT\20210101-20251231-2.csv"

def simulate():
    print("=== FUND MANAGEMENT SIMULATION (2021-2024) ===")
    
    # 1. Load & Prepare Data (Same as previous steps)
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
        
        # Sort Chronologically
        if 'Date' in df.columns:
            df = df.sort_values('Date')
        
    except Exception as e:
        print(f"Prophet Error: {e}")
        return

    # 2. Simulation Logic
    strategies = [
        {"name": "A: Safety First (Shrink on Loss)", "ev_min": 1.34, "shrink": True},
        {"name": "B: Endurance (Fixed Cap)",         "ev_min": 1.34, "shrink": False},
        {"name": "C: Quality (High EV > 2.0)",       "ev_min": 2.0,  "shrink": False}
    ]
    
    for strat in strategies:
        print(f"\nrunning Strategy: {strat['name']}...")
        run_strategy(df.copy(), strat)

def run_strategy(df, params):
    # Filter by EV
    candidates = df[df['ev'] > params['ev_min']].copy()
    
    # Group by Date
    dates = candidates['Date'].unique()
    
    # Wallet State
    wallet = 0 # Net Profit/Loss
    daily_cap_base = 10000
    current_daily_cap = daily_cap_base
    
    history_pnl = []
    daily_caps = []
    
    total_bets = 0
    total_wins = 0
    
    for d in dates:
        # Get bets for this day
        day_bets = candidates[candidates['Date'] == d]
        
        day_spend = 0
        day_return = 0
        
        # Determine Stake per Bet for today
        # Simple rule: Yield efficient? Fixed cost?
        # Let's say Fixed 1,000 JPY per bet, capped by Daily Limit.
        STAKE_PER_BET = 1000 
        
        bets_placed = 0
        
        for _, row in day_bets.iterrows():
            if day_spend + STAKE_PER_BET > current_daily_cap:
                break # Stop for day
            
            day_spend += STAKE_PER_BET
            bets_placed += 1
            
            if row['is_win'] == 1:
                payout = int(STAKE_PER_BET * row['単勝オッズ'])
                day_return += payout
                total_wins += 1
            
            total_bets += 1
            
        day_pnl = day_return - day_spend
        wallet += day_pnl
        history_pnl.append(wallet)
        daily_caps.append(current_daily_cap)
        
        # Fund Adjustment Logic
        if params['shrink']:
            # Safety First: If Day Loss -> Halve Cap vs Base? Or Halve Previous?
            # "Shrinking" usually means reacting to drawdown.
            # User said: "Daily loss cut, next day investment reduction".
            
            if day_pnl < 0:
                # Loss Day: Reduce Cap for tomorrow
                # Floor at 1000 JPY (1 bet)
                current_daily_cap = max(1000, int(current_daily_cap * 0.5))
            else:
                # Winning Day: Recover Cap?
                # Usually step-up or full reset. User assumes full recovery is hard.
                # Let's say we recover slowly (doubling back) or Full Reset.
                # To demonstrate "Jiri-hin" (Death Spiral), assume slowly?
                # Actually, if we hit a big win (50x), day_pnl is HUGE (+49,000).
                # Logic: Reset to Base on Win.
                current_daily_cap = daily_cap_base
        else:
            # Fixed Cap always
            current_daily_cap = daily_cap_base

    # Report
    final_pnl = wallet
    max_dd = 0
    peak = 0
    for val in history_pnl:
        if val > peak: peak = val
        dd = peak - val
        if dd > max_dd: max_dd = dd
        
    print(f"  Final PnL: JPY {final_pnl:,}")
    print(f"  Max Drawdown: -JPY {max_dd:,}")
    print(f"  Total Bets: {total_bets} (Wins: {total_wins})")
    
    # Specific Check for Strategy A (Death Spiral)
    if params['shrink']:
        print(f"  Final Daily Cap: JPY {current_daily_cap}")
        # Did we miss potential profit?
        # Compare with Strategy B (same bets, different caps)
        # Note: Strategy B places MORE bets if Strategy A was capped.
        pass

if __name__ == "__main__":
    simulate()
