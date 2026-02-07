from jra_specs import SPECS

class JRAParser:
    def __init__(self, line_str):
        # 入力データを cp932 (Shift-JIS) の bytes に変換して保持
        try:
            self.data = line_str.encode('cp932')
        except UnicodeEncodeError:
            self.data = line_str.encode('utf-8', errors='replace')

    def get_str(self, start, length):
        """指定バイト位置を切り出し、cp932でデコードして空白除去"""
        try:
            chunk = self.data[start : start + length]
            return chunk.decode('cp932', errors='replace').strip()
        except:
            return ""

    def parse(self, data_type):
        """引数 data_type と Record Spec に応じて解析を行い、辞書を返す"""
        if data_type not in SPECS:
            return None
            
        spec_config = SPECS[data_type]
        record_type = self.get_str(0, 2)
        res = {"record_type": record_type}
        
        # 1. Selector 形式 (レコード種別ごとに定義が異なる場合)
        if spec_config["type"] == "selector":
            if record_type not in spec_config["specs"]:
                return None # 定義にないレコード(RA等)はスキップ
            
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
