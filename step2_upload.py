
import os
import glob
import json
import base64
import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from jra_parser import JRAParser

# Load Environment Variables
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def process_and_upload():
    print("=== Step 2: Strict Byte Upload to Supabase ===")
    
    # 1. Look for text files in jv_data/
    # jv_data へのパスを特定
    jv_dir = "jv_data"
    if not os.path.exists(jv_dir):
        # ワークスペースに合わせてフォールバック
        jv_dir = r"C:\TFJV\my-racing-dashboard\jv_data"
        if not os.path.exists(jv_dir):
            print(f"Error: Directory {jv_dir} not found.")
            return

    files = glob.glob(os.path.join(jv_dir, "*.txt"))
    
    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"Processing: {filename}")
        
        # 2. Identify data type and date from filename
        # Expecting format like: 0B15_20260207.txt
        if '_' not in filename:
            print(f"   Skipping {filename}: Unexpected format.")
            continue
            
        parts = filename.split('_')
        data_type = parts[0]
        date_str = parts[1].replace('.txt', '')
        
        # 0B15, 0B12, 0B30, 0B31 以外は無視
        target_types = ['0B15', '0B12', '0B30', '0B31']
        if data_type not in target_types:
            print(f"   Skipping {filename}: Not a target type.")
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"   Error reading file: {e}")
            continue
            
        records = []
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Record type prefix check (RA, SE, HR, etc.)
            # RA, SE, HR, O* etc. according to specs
            # JRAParser handles prefix specific logic internally if needed
            
            # 3. Use JRAParser to convert line to dict
            parser = JRAParser(line)
            parsed_content = parser.parse(data_type)
            
            # race_id が取得できないものはスキップ
            race_id = parsed_content.get("race_id")
            if not race_id or race_id == "UNKNOWN": 
                continue
            
            # Store in content (JSONB)
            # Table schema uses race_date and data_type
            record = {
                "race_id": race_id,
                "race_date": date_str,
                "data_type": data_type,
                "content": json.dumps(parsed_content, ensure_ascii=False),
                "raw_string": base64.b64encode(line.encode('utf-8')).decode('utf-8')
            }
            records.append(record)
            
        # 4. Batch Upload to Supabase
        if records:
            print(f"   Uploading {len(records)} records for {data_type}...")
            BATCH_SIZE = 100
            success_count = 0
            try:
                for i in range(0, len(records), BATCH_SIZE):
                    batch = records[i:i+BATCH_SIZE]
                    # raw_race_data テーブルに upsert
                    supabase.table("raw_race_data").upsert(batch).execute()
                    success_count += len(batch)
                print(f"   Successfully uploaded {success_count} records.")
            except Exception as e:
                print(f"   Upload Fail: {e}")

if __name__ == "__main__":
    process_and_upload()
    print("All tasks completed.")
