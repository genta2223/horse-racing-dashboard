
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
        res = {}
        
        # 共通項目: race_id
        # Year(11,4) + Month(15,2) + Day(17,2) + Place(19,2) + Kai(21,2) + Nichi(23,2) + Race(25,2)
        year = self.get_str(11, 4)
        month = self.get_str(15, 2)
        day = self.get_str(17, 2)
        place = self.get_str(19, 2)
        kai = self.get_str(21, 2)
        nichi = self.get_str(23, 2)
        race = self.get_str(25, 2)
        res["race_id"] = f"{year}{month}{day}{place}{kai}{nichi}{race}"

        if data_type == '0B15':
            res["Umaban"] = self.get_str(28, 2)
            res["horse_num"] = res["Umaban"] # Alias for consistency
            res["Horse"] = self.get_str(68, 36) 
            res["horse_name"] = res["Horse"] # Alias
            res["Jockey"] = self.get_str(134, 12)
            res["jockey"] = res["Jockey"] # Alias
            res["Trainer"] = self.get_str(178, 12)
            res["Weight"] = self.get_str(122, 3)
            # 斤量は10倍された値なので変換
            if res["Weight"].isdigit():
                res["Weight"] = f"{int(res['Weight'])/10:.1f}"
            
        elif data_type == '0B12':
            res["rank_1_horse"] = self.get_str(148, 2)
            res["pay_tan"] = self.get_str(382, 7)
            
        elif data_type in ['0B30', '0B31']:
            # オッズデータ特有のヘッダー情報（登録頭数など）
            # 通常、JV-Linkのオッズデータ(0B31)はヘッダー部に登録頭数(55-57)がある
            registered_horses_str = self.get_str(55, 2)
            registered_horses = int(registered_horses_str) if registered_horses_str.isdigit() else 0
            
            res["registered_horses"] = registered_horses
            odds_list = []
            
            # 繰り返し部: 開始位置 66byte, 各馬データ長 15byte
            for i in range(registered_horses):
                offset = 66 + (i * 15)
                # バイト配列の範囲を超えないかチェック
                if offset + 15 > len(self.data):
                    break
                    
                horse_odds = {
                    "horse_num": self.get_str(offset, 2),
                    "tan_odds": self.get_str(offset + 2, 4)
                }
                odds_list.append(horse_odds)
            
            res["odds"] = odds_list
            
        return res
