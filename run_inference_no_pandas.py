from supabase import create_client
import datetime
import random
import time

def run_test():
    print("[TEST] Starting End-to-End Inference Test (No Pandas Mode)...")
    
    # 1. Connect Supabase
    SUPABASE_URL = "https://dlhcauiwyratanbhxdnp.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsaGNhdWl3eXJhdGFuYmh4ZG5wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyNjA4ODIsImV4cCI6MjA4NTgzNjg4Mn0.dPmKQAv8UZfpHezwCpSLgSAKOab5c0iw-_aJt8DqML0"
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except ImportError:
        print("[ERROR] Supabase library not found!")
        return

    # 2. Check Raw Data
    print("[TEST] Verifying Raw Data Upload...")
    try:
        res = supabase.table("raw_race_data").select("count", count="exact").execute()
        count = res.count if hasattr(res, 'count') else "Unknown"
        print(f"   Row Count in DB: {count}")
    except Exception as e:
        print(f"[WARN] DB Check Failed: {e}")

    # 3. Prepare Mock Data (List of Dicts)
    print("[TEST] Generating Mock Features for 2026-02-07...")
    mock_data = []
    race_id_mock = "202602070501" # Tokyo 1R
    
    # Mocking Brain Logic with pure Python
    print("[TEST] Using Simulated Prediction (Brain Skipped due to Env)...")
    
    queue_items = []
    for horse_num in range(1, 17):
        odds = random.uniform(1.5, 50.0)
        
        # Simulating Probe
        ai_prob = random.uniform(0.0, 0.5)
        # Force a hit on Horse 7
        if horse_num == 7:
            ai_prob = 0.4
            odds = 4.0 # EV = 1.6
            
        ev = ai_prob * odds
        
        if ev > 1.34:
            print(f"   >>> HIT! Horse {horse_num} EV ({ev:.2f}) > 1.34")
            
            bet = {
                "race_id": race_id_mock,
                "horse_num": horse_num,
                "bet_type": "WIN",
                "amount": 100,
                "status": "approved",
                "created_at": str(datetime.datetime.now())
            }
            queue_items.append(bet)

    # 4. Insert
    if queue_items:
        print(f"[TEST] Inserting {len(queue_items)} bets to Queue...")
        try:
            res = supabase.table("bet_queue").insert(queue_items).execute()
            print("[TEST] Insert Success.")
            
            # 5. Report Top 5 (from memory since we don't query back)
            print("\n[REPORT] Top Recommended Bets (Simulated):")
            for item in queue_items[:5]:
                print(f" - Race: {item['race_id']} Horse: {item['horse_num']} Amount: {item['amount']}")
                
        except Exception as e:
            print(f"[ERROR] Queue Insert Failed: {e}")
    else:
        print("[TEST] No High EV Horses found.")

if __name__ == "__main__":
    run_test()
