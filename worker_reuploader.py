import os
import glob
import json
import base64
import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# 環境変数読み込み
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

class JRAByteParser:
    def __init__(self, line_str):
        # 入力を強制的にShift-JISバイト列に変換
        try:
            self.data = line_str.encode('cp932')
        except UnicodeEncodeError:
            self.data = line_str.encode('utf-8', 'ignore') # 安全策

    def get_val(self, start, length):
        # バイト位置でスライス -> Shift-JISデコード -> トリム
        try:
            chunk = self.data[start : start + length]
            return chunk.decode('cp932', errors='replace').strip().replace('\u3000', ' ')
        except:
            return ""

def parse_0b15_se(line_str):
    p = JRAByteParser(line_str)
    
    # Race ID構成: Year(11,4) + Month(15,2) + Day(17,2) + Place(19,2) + Kai(21,2) + Nichi(23,2) + Race(25,2)
    year = p.get_val(11, 4)
    month = p.get_val(15, 2)
    day = p.get_val(17, 2)
    place = p.get_val(19, 2)
    kai = p.get_val(21, 2)
    nichi = p.get_val(23, 2)
    race = p.get_val(25, 2)
    
    race_id = f"{year}{month}{day}{place}{kai}{nichi}{race}"
    
    # 馬情報
    horse_num = p.get_val(28, 2)
    horse_name = p.get_val(68, 36)
    sex_code = p.get_val(46, 1)
    jockey = p.get_val(134, 12)
    trainer = p.get_val(178, 12)
    weight_raw = p.get_val(122, 3)
    
    # 斤量変換 (例: "580" -> 58.0)
    weight = weight_raw
    if weight.isdigit():
        weight = f"{int(weight)/10:.1f}"

    return {
        "record_type": "SE",
        "race_id": race_id,
        "Umaban": horse_num,
        "Horse": horse_name,
        "Sex": sex_code,
        "Jockey": jockey,
        "Trainer": trainer,
        "Weight": weight,
        "raw_prefix": line_str[:10]
    }

def parse_0b12_hr(line_str):
    p = JRAByteParser(line_str)
    
    # Race ID構成
    year = p.get_val(11, 4)
    month = p.get_val(15, 2)
    day = p.get_val(17, 2)
    place = p.get_val(19, 2)
    kai = p.get_val(21, 2)
    nichi = p.get_val(23, 2)
    race = p.get_val(25, 2)
    
    race_id = f"{year}{month}{day}{place}{kai}{nichi}{race}"
    
    # 結果情報
    rank_1 = p.get_val(148, 2)
    rank_2 = p.get_val(150, 2)
    pay_tan_raw = p.get_val(382, 7)
    
    pay_tan = 0
    if pay_tan_raw.isdigit():
        pay_tan = int(pay_tan_raw)

    return {
        "record_type": "HR",
        "race_id": race_id,
        "rank_1_horse": rank_1,
        "rank_2_horse": rank_2,
        "pay_tan": pay_tan,
        "raw_prefix": line_str[:10]
    }

def process_file(file_path):
    filename = os.path.basename(file_path)
    print(f"Processing: {filename}")
    
    data_type = ""
    if "0B15" in filename:
        data_type = "0B15"
    elif "0B12" in filename:
        data_type = "0B12"
    else:
        return

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    records = []
    for line in lines:
        line = line.strip()
        if not line: continue
        
        parsed_content = {}
        if data_type == "0B15" and line.startswith("SE"):
            parsed_content = parse_0b15_se(line)
        elif data_type == "0B12" and line.startswith("HR"):
            parsed_content = parse_0b12_hr(line)
        else:
            continue

        if not parsed_content: continue
        
        race_id = parsed_content.get("race_id", "UNKNOWN")
        
        # Raw String (Base64)
        raw_b64 = base64.b64encode(line.encode('utf-8')).decode('utf-8')
        
        record = {
            "race_id": race_id,
            "race_date": race_id[:8],
            "data_type": data_type,
            "raw_string": raw_b64,
            "content": parsed_content
        }
        records.append(record)

    if records:
        print(f"Uploading {len(records)} records for {data_type}...")
        # バッチ処理 (100件ずつ)
        BATCH_SIZE = 100
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i+BATCH_SIZE]
            supabase.table("raw_race_data").upsert(batch).execute()

def main():
    print("=== JRA-VAN Data Re-uploader ===")
    jv_dir = "jv_data"
    if not os.path.exists(jv_dir):
        print(f"Directory {jv_dir} not found.")
        return

    files = glob.glob(os.path.join(jv_dir, "*.txt"))
    for f in files:
        process_file(f)
    print("All tasks completed.")

if __name__ == "__main__":
    main()
