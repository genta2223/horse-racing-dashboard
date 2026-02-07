import os
import sys
import time
import json
import datetime
import requests
from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Supabase credentials missing.")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_today_str():
    return datetime.datetime.now().strftime("%Y%m%d")

def scrape_race_results(race_id):
    """
    Scrapes race result from netkeiba (Example structure)
    Note: Structure is subject to change.
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Parse Ranking
        # Table ID: All_Result_Table
        table = soup.find("table", id="All_Result_Table")
        if not table:
            return None
        
        update_data = {
            "race_id": race_id,
            "race_date": race_id[:8],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Extract Top 3 Horses
        rows = table.find_all("tr", class_="HorseList")
        for i, row in enumerate(rows[:3]):
            try:
                # Horse Num is usually in a td with class "Num" or specific index
                # Netkeiba structure: 0:Rank, 1:Waku, 2:Num, ...
                cols = row.find_all("td")
                if len(cols) > 3:
                    rank_val = i + 1
                    horse_num = int(cols[2].get_text(strip=True))
                    update_data[f"rank_{rank_val}_horse_num"] = horse_num
            except:
                pass

        # Parse Payouts (Pay_Table)
        # Netkeiba has multiple tables for payouts. Usually class "Pay_Table"
        pay_tables = soup.find_all("table", class_="Pay_Table")
        if pay_tables:
            # Usually Table 1: Tan/Fuku, Table 2: Waku/Umaren/Wide/Umatan/Sanren
            
            # Simple Parser for Tan (Win)
            try:
                # Structure varies, implementing basic extraction logic
                # Finding '単勝' row
                for pt in pay_tables:
                    rows = pt.find_all("tr")
                    for row in rows:
                        header = row.find("th")
                        if not header: continue
                        title = header.get_text(strip=True)
                        
                        if "単勝" in title:
                            # Extract Payout
                            # <td class="Payout"><span>230</span></td>
                            payout_raw = row.find("td", class_="Payout").get_text(strip=True).replace(",", "")
                            update_data["pay_tan"] = int(payout_raw)
                        
                        elif "複勝" in title:
                            # Fuku can have multiple lines
                            payouts_raw = row.find("td", class_="Payout").stripped_strings
                            fuku_pays = [int(p.replace(",", "")) for p in payouts_raw]
                            update_data["pay_fuku"] = fuku_pays
                            
                        elif "馬連" in title:
                            payout_raw = row.find("td", class_="Payout").get_text(strip=True).replace(",", "")
                            update_data["pay_umaren"] = int(payout_raw)
                            
                        elif "馬単" in title:
                            payout_raw = row.find("td", class_="Payout").get_text(strip=True).replace(",", "")
                            update_data["pay_umatan"] = int(payout_raw)
                            
                        elif "ワイド" in title:
                            payouts_raw = row.find("td", class_="Payout").stripped_strings
                            wide_pays = [int(p.replace(",", "")) for p in payouts_raw]
                            update_data["pay_wide"] = wide_pays

            except Exception as e:
                print(f"[WARN] Payout parse error: {e}")
        
        return update_data

    except Exception as e:
        print(f"[ERROR] Scrape failed for {race_id}: {e}")
        return None

def main():
    print("Starting Result Scraper...")
    
    # 1. Get today's races from Supabase (to know what to scrape)
    # OR iterate all potential race_ids for today
    
    # Efficient approach: Check raw_race_data for today's race_ids
    today_str = get_today_str()
    
    # For testing, let's look at recent data in DB
    # In production, this would look for today's races
    
    try:
        # Get pending races or races from today
        # We need a list of race_ids to check. 
        # For hybrid model, we rely on having 0B15 data uploaded.
        
        res = supabase.table("raw_race_data").select("race_id").eq("race_date", today_str).execute()
        
        if not res.data:
            print("No races found in DB for today. Nothing to scrape.")
            return

        race_ids = [r['race_id'] for r in res.data]
        # Unique
        race_ids = list(set(race_ids))
        print(f"Checking {len(race_ids)} races for results...")
        
        for rid in race_ids:
            # Check if result already exists? 
            # Or just overwrite (upsert) to ensure latest
            
            result_data = scrape_race_results(rid)
            if result_data:
                # Upsert to race_results
                supabase.table("race_results").upsert(result_data).execute()
                print(f"[OK] Updates results for {rid}")
            else:
                print(f"[SKIP] No result yet for {rid}")
            
            time.sleep(1) # Be polite
            
    except Exception as e:
        print(f"[ERROR] Main loop: {e}")

if __name__ == "__main__":
    main()
