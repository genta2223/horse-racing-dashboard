
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 環境変数読み込み
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def main():
    print("=== Database Cleanup (Truncate raw_race_data) ===")
    try:
        # Supabase RPC or direct DELETE (since TRUNCATE isn't always exposed)
        # For small data, delete all rows is fine.
        # res = supabase.table("raw_race_data").delete().neq("race_id", "xxxx").execute() 
        # Using RPC if available is better, or a broad DELETE filter
        supabase.table("raw_race_data").delete().neq("data_type", "NONE").execute()
        print("Successfully cleaned the table.")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    main()
