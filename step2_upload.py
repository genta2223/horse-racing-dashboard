
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
    print("=== Step 2: Specification-Driven Data Upload ===")
    
    # jv_data への絶対パス
    jv_dir = r"C:\TFJV\my-racing-dashboard\jv_data"
    if not os.path.exists(jv_dir):
        # Local fallback
        jv_dir = "jv_data"
        if not os.path.exists(jv_dir):
            print(f"Error: Directory {jv_dir} not found.")
            return

    # 対応データ種別
    target_types = ['0B15', '0B12', '0B30', '0B31']
    
    files = glob.glob(os.path.join(jv_dir, "*.txt"))
    
    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"Processing: {filename}")
        
        # ファイル名からデータ種別と日付を特定
        if '_' not in filename: continue
        parts = filename.split('_')
        data_type = parts[0]
        date_str = parts[1].replace('.txt', '')
        
        if data_type not in target_types:
            continue

        try:
            # Open in binary mode to preserve original Shift-JIS / Byte Map layout
            with open(file_path, "rb") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"   Error reading file: {e}")
            continue
            
        records = []
        for line in lines:
            # Keep original bytes without stripping (fixed length records)
            if not line: continue
            
            # JRAParser handles bytes directly now
            parser = JRAParser(line)
            parsed_content = parser.parse(data_type)
            
            # None の場合はスキップ
            if parsed_content is None:
                continue
            
            race_id = parsed_content.get("race_id")
            if not race_id or race_id == "UNKNOWN": 
                continue
            
            # Content カラムに辞書データを格納
            # raw_string カラムにはオリジナルのバイナリをBase64で保存
            record = {
                "race_id": race_id,
                "race_date": date_str,
                "data_type": data_type,
                "content": json.dumps(parsed_content, ensure_ascii=False),
                "raw_string": base64.b64encode(line).decode('utf-8')
            }
            records.append(record)
            
        if records:
            print(f"   Uploading {len(records)} records for {data_type}...")
            BATCH_SIZE = 100
            success_count = 0
            try:
                for i in range(0, len(records), BATCH_SIZE):
                    batch = records[i:i+BATCH_SIZE]
                    supabase.table("raw_race_data").upsert(batch).execute()
                    success_count += len(batch)
                print(f"   Successfully uploaded {success_count} records.")
            except Exception as e:
                print(f"   Upload Fail: {e}")

if __name__ == "__main__":
    process_and_upload()
    print("All tasks completed.")
