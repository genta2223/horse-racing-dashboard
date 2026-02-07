from jra_specs import SPECS

class JRAParser:
    def __init__(self, data):
        # データの型に応じてバイト型に統一
        if isinstance(data, str):
            self.data = data.encode('cp932', errors='replace')
        else:
            self.data = data

    def get_str(self, start, length):
        """指定バイト位置を切り出し、cp932でデコードして空白除去"""
        try:
            chunk = self.data[start : start + length]
            return chunk.decode('cp932', errors='replace').strip()
        except:
            return ""

    def parse(self, data_type):
        """引数 data_type と Record Spec に応じて厳格な解析を行い、辞書を返す"""
        if data_type not in SPECS:
            return None
            
        spec_config = SPECS[data_type]
        record_type = self.get_str(0, 2)     # 先頭2バイト
        data_div = self.get_str(2, 1)        # 3バイト目 (データ区分)
        
        # --- Strict Gatekeeper: Validation Logic ---
        
        # 0B15 (出馬表): SE かつ データ区分 '7' (確定) のみ許可
        if data_type == "0B15":
            if record_type != "SE":
                return None
            if data_div not in ["2", "7"]:
                # '2'(前日) または '7'(確定) のみを許可
                print(f"[REJECTED] Skipped invalid data div: {record_type}{data_div} (Strictly 2 or 7 only)")
                return None

        # 0B12 (成績): SE または HR のみ許可
        elif data_type == "0B12":
            if record_type not in ["SE", "HR"]:
                return None # Skip noise (RA, H1 etc.)

        # 0B30/31 (オッズ): オッズレコード以外は弾く
        elif data_type in ["0B30", "0B31"]:
            if not record_type.startswith("O"):
                return None

        # --- End of Validation ---

        res = {"record_type": record_type, "data_division": data_div}
        
        # 1. Selector 形式 (レコード種別ごとに定義が異なる場合)
        if spec_config["type"] == "selector":
            if record_type not in spec_config["specs"]:
                return None
            
            target_spec = spec_config["specs"][record_type]
            for col, pos in target_spec["columns"].items():
                res[col] = self.get_str(pos["start"], pos["len"])
                
        # 2. Fixed 形式 (単独レコード)
        elif spec_config["type"] == "fixed":
            # 有効なレコード種別のチェック
            valid_types = spec_config.get("valid_record_types", [])
            if valid_types and record_type not in valid_types:
                return None
                
            for col, pos in spec_config["columns"].items():
                res[col] = self.get_str(pos["start"], pos["len"])
                
        # 3. Loop 形式 (オッズデータ等)
        elif spec_config["type"] == "loop":
            header_len = spec_config["header_len"]
            item_len = spec_config["item_len"]
            
            # 登録頭数 (通常55-57バイト目にある)
            reg_horses_str = self.get_str(55, 2)
            reg_horses = int(reg_horses_str) if reg_horses_str.isdigit() else 0
            res["registered_horses"] = reg_horses
            
            items = []
            for i in range(reg_horses):
                item_start = header_len + (i * item_len)
                if item_start + item_len > len(self.data):
                    break
                    
                item_data = {}
                for col, pos in spec_config["columns"].items():
                    item_data[col] = self.get_str(item_start + pos["start"], pos["len"])
                items.append(item_data)
            
            res["odds"] = items

        # 共通処理: race_id の生成 (全種別共通のバイト位置 11-26を使用)
        if "race_id" not in res:
            year = self.get_str(11, 4)
            month = self.get_str(15, 2)
            day = self.get_str(17, 2)
            place = self.get_str(19, 2)
            kai = self.get_str(21, 2)
            nichi = self.get_str(23, 2)
            race = self.get_str(25, 2)
            res["race_id"] = f"{year}{month}{day}{place}{kai}{nichi}{race}"
            
        return res
