import os
import requests
from dotenv import load_dotenv

# Load Env
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Missing SUPABASE credentials.")
    exit(1)

TARGET_DATE = "20260208"

def clean_target_date():
    print(f"Cleaning data for {TARGET_DATE}...")
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    # Count before
    count_url = f"{url}/rest/v1/raw_race_data?select=count&race_date=eq.{TARGET_DATE}"
    # Supabase returns count in header 'Content-Range' usually if Prefer: count=exact, or simply count items
    # But let's just use select=id with HEAD or select=count
    # Actually, simplest is to check len(GET)
    r = requests.get(f"{url}/rest/v1/raw_race_data", headers=headers, params={"select": "race_date", "race_date": f"eq.{TARGET_DATE}"})
    if r.status_code == 200:
        count_before = len(r.json())
        print(f"Records before: {count_before}")
    else:
        print(f"Error checking count: {r.text}")
        count_before = -1
    
    if count_before > 0:
        # DELETE
        # Need to include filters in query params
        del_url = f"{url}/rest/v1/raw_race_data"
        r = requests.delete(del_url, headers=headers, params={"race_date": f"eq.{TARGET_DATE}"})
        
        if r.status_code in (200, 204):
            print("Delete request sent successfully.")
        else:
            print(f"Delete failed: {r.status_code} {r.text}")
            
        # Verify
        r = requests.get(f"{url}/rest/v1/raw_race_data", headers=headers, params={"select": "race_date", "race_date": f"eq.{TARGET_DATE}"})
        count_after = len(r.json())
        print(f"Records after delete: {count_after}")
    else:
        print("No records found to delete.")

if __name__ == "__main__":
    clean_target_date()
