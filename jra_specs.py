# jra_specs.py
# JRA-VAN Data Byte Map Definitions (Shift-JIS)

SPECS = {
    "0B15": { # 出馬表 (RT Spec Empirical)
        "type": "fixed",
        "valid_record_types": ["SE"],
        "columns": {
            "race_id_part": {"start": 11, "len": 16},
            "waku":         {"start": 27, "len": 1},
            "horse_num":    {"start": 28, "len": 2},
            "horse_name":   {"start": 40, "len": 28},
            "sex_code":     {"start": 297, "len": 1},
            "hair_code":    {"start": 298, "len": 2},
            "age":          {"start": 300, "len": 1},
            "weight":       {"start": 288, "len": 3},
            "jockey":       {"start": 306, "len": 12},
        }
    },
    "0B12": { # 成績 (セレクター形式)
        "type": "selector",
        "specs": {
            "SE": { # 馬ごとの成績
                "columns": {
                    "race_id_part": {"start": 11, "len": 16},
                    "horse_num":    {"start": 28, "len": 2},
                    "rank":         {"start": 148, "len": 2}, # 確定着順 (RT spec TBD)
                }
            },
            "HR": { # 払戻金 (Payoff)
                "columns": {
                    "race_id_part": {"start": 11, "len": 16},
                    "pay_tan":      {"start": 382, "len": 7},
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
