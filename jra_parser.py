from jra_specs import SPECS

class JRAParser:
    def __init__(self, line_str):
        # 入力データを cp932 (Shift-JIS) の bytes に変換して保持
        try:
            self.data = line_str.encode('cp932')
        except UnicodeEncodeError:
            # Shift-JISでエンコードできない文字が含まれる場合は
            # エラー回避のために utf-8 でエンコード (通常JRAデータでは発生しない)
            self.data = line_str.encode('utf-8', errors='replace')

    def get_str(self, start, length):
        """指定バイト位置を切り出し、cp932でデコードして空白除去"""
        try:
            chunk = self.data[start : start + length]
            # decode時にエラー文字があれば '?' などに置き換える
            return chunk.decode('cp932', errors='replace').strip()
        except:
            return ""

    def parse(self, data_type):
        """引数 data_type に応じて解析を行い、辞書を返す"""
        if data_type not in SPECS:
            return {}
            
        spec = SPECS[data_type]
        res = {}
        
        if spec["type"] == "fixed":
            # 固定長カラムの抽出
            for col, pos in spec["columns"].items():
                res[col] = self.get_str(pos["start"], pos["len"])
            
            # race_id の追加処理 (仕様：Year(11,4) + Month(15,2) + Day(17,2) + Place(19,2) + Kai(21,2) + Nichi(23,2) + Race(25,2))
            if "race_id_part" in res:
                p = res["race_id_part"] # 0-27バイト
                # ユーザー要求のRaceID構成：Year(11,4)...
                # self.data から直接切り出す方が確実
                year = self.get_str(11, 4)
                month = self.get_str(15, 2)
                day = self.get_str(17, 2)
                place = self.get_str(19, 2)
                kai = self.get_str(21, 2)
                nichi = self.get_str(23, 2)
                race = self.get_str(25, 2)
                res["race_id"] = f"{year}{month}{day}{place}{kai}{nichi}{race}"
                
        elif spec["type"] == "loop":
            # ループ構造 (オッズ等)
            header_len = spec["header_len"]
            item_len = spec["item_len"]
            
            # race_id (オッズデータもヘッダー構成は同じ)
            year = self.get_str(11, 4)
            month = self.get_str(15, 2)
            day = self.get_str(17, 2)
            place = self.get_str(19, 2)
            kai = self.get_str(21, 2)
            nichi = self.get_str(23, 2)
            race = self.get_str(25, 2)
            res["race_id"] = f"{year}{month}{day}{place}{kai}{nichi}{race}"
            
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
                for col, pos in spec["columns"].items():
                    item_data[col] = self.get_str(item_start + pos["start"], pos["len"])
                items.append(item_data)
            
            res["odds"] = items
            
        return res
