# jra_specs.py
# JRA-VAN Data Byte Map Definitions (Shift-JIS)

SPECS = {
    "0B15": { # 出馬表
        "type": "fixed",
        "valid_record_types": ["SE"],
        "columns": {
            "race_id_part": {"start": 0, "len": 27},
            "horse_num":    {"start": 28, "len": 2},
            "sex_code":     {"start": 46, "len": 1},
            "hair_code":    {"start": 47, "len": 2},
            "horse_name":   {"start": 68, "len": 36},
            "weight":       {"start": 122, "len": 3},
            "jockey":       {"start": 134, "len": 12},
            "trainer":      {"start": 178, "len": 12},
        }
    },
    "0B12": { # 成績 (セレクター形式)
        "type": "selector",
        "specs": {
            "SE": { # 馬ごとの成績
                "columns": {
                    "race_id_part": {"start": 0, "len": 27},
                    "horse_num":    {"start": 28, "len": 2},
                    "rank":         {"start": 148, "len": 2}, # 確定着順
                }
            },
            "HR": { # 払戻金 (Payoff)
                "columns": {
                    "race_id_part": {"start": 0, "len": 27},
                    "pay_tan":      {"start": 382, "len": 7},
                    "pay_data":     {"start": 28, "len": 400}, # 払戻情報全体
                }
            }
        }
    },
    "0B30": { # オッズ
        "type": "loop",
        "header_len": 66,
        "item_len": 15,
        "columns": {
            "horse_num": {"start": 0, "len": 2},
            "odds_tan":  {"start": 2, "len": 4},
            "pop_tan":   {"start": 6, "len": 2},
        }
    },
    "0B31": { # オッズ
        "type": "loop",
        "header_len": 66,
        "item_len": 15,
        "columns": {
            "horse_num": {"start": 0, "len": 2},
            "odds_tan":  {"start": 2, "len": 4},
            "pop_tan":   {"start": 6, "len": 2},
        }
    }
}
