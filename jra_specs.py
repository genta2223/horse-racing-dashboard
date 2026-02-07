# jra_specs.py
# JRA-VAN Data Byte Map Definitions (Shift-JIS)

SPECS = {
    "0B15": { # 出馬表
        "type": "fixed",
        "columns": {
            "race_id_part": {"start": 0, "len": 27}, # ID生成用
            "horse_num":    {"start": 28, "len": 2},
            "sex_code":     {"start": 46, "len": 1},
            "hair_code":    {"start": 47, "len": 2},
            "horse_name":   {"start": 68, "len": 36}, # 全角18文字
            "weight":       {"start": 122, "len": 3},
            "jockey":       {"start": 134, "len": 12},
            "trainer":      {"start": 178, "len": 12},
        }
    },
    "0B12": { # 成績
        "type": "fixed",
        "columns": {
            "race_id_part": {"start": 0, "len": 27},
            "rank_1_horse": {"start": 148, "len": 2},
            "rank_2_horse": {"start": 150, "len": 2},
            "pay_tan":      {"start": 382, "len": 7},
        }
    },
    "0B30": { # オッズ（ループ構造）
        "type": "loop",
        "header_len": 66,
        "item_len": 15,
        "columns": {
            "horse_num":    {"start": 0, "len": 2}, # offset relative to item start
            "odds_tan":     {"start": 2, "len": 4},
            "pop_tan":      {"start": 6, "len": 2},
        }
    },
    "0B31": { # オッズ（ループ構造） 0B30と同様
        "type": "loop",
        "header_len": 66,
        "item_len": 15,
        "columns": {
            "horse_num":    {"start": 0, "len": 2},
            "odds_tan":     {"start": 2, "len": 4},
            "pop_tan":      {"start": 6, "len": 2},
        }
    }
}
