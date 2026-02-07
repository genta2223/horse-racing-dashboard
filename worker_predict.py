
import os
import sys
import json
import argparse
import datetime
import pandas as pd
import joblib
from dotenv import load_dotenv
import requests

# --- 1. Setup ---
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

MODEL_PATH = "local_engine/final_model.pkl"

def supabase_query(table, select="*", filters=None):
    """requests を使用して Supabase API を直接叩く"""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    # 簡易的なクエリ構築 (eq フィルタのみサポート)
    params = {"select": select}
    if filters:
        for k, v in filters.items():
            if isinstance(v, list):
                # in フィルタ構文: in.(value1,value2)
                params[k] = f"in.({','.join(v)})"
            else:
                params[k] = f"eq.{v}"
    
    rest_url = f"{url}/rest/v1/{table}"
    try:
        response = requests.get(rest_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        # print(f"[DEBUG] API Query: {table} -> {len(data)} records") # Debugging line, commented out as per instruction snippet
        return data
    except Exception as e:
        print(f"[ERROR] API Query Fail: {e}")
        return []

def load_prediction_model():
    """学習済みモデルをロードする。存在しない場合は None を返す。"""
    if os.path.exists(MODEL_PATH):
        try:
            import sklearn # scikit-learn モデルのロードに必要
            model = joblib.load(MODEL_PATH)
            print(f"[INFO] モデルをロードしました: {MODEL_PATH}")
            return model
        except Exception as e:
            print(f"[WARN] モデルのロードに失敗しました: {e}")
    else:
        print("[INFO] モデルファイルが見つかりません。ルールベースロジックを使用します。")
    return None

def fetch_data(date_str):
    """指定日のデータを取得し、結合したDataFrameを返す"""
    print(f"[INFO] データ取得中 (REST API): {date_str}")
    
    # 0B15 (出馬表)
    res_h = supabase_query("raw_race_data", select="race_id, content", filters={"data_type": "0B15", "race_date": date_str})
    # 0B30 (オッズ)
    res_o = supabase_query("raw_race_data", select="race_id, content", filters={"data_type": ["0B30", "0B31"], "race_date": date_str})
    
    if not res_h:
        print(f"[ERROR] {date_str} の出馬表データが見つかりません。")
        return pd.DataFrame()

    # Horses
    horses = []
    for r in res_h:
        rid = r['race_id']
        c = json.loads(r['content'])
        if c.get('record_type') == 'SE':
            h_row = c.copy()
            h_row['race_id'] = rid
            h_row['horse_num'] = str(h_row.get('horse_num', '')).zfill(2)
            horses.append(h_row)
    
    df_h = pd.DataFrame(horses)
    
    # Odds
    odds = []
    if res_o:
        for r in res_o:
            rid = r['race_id']
            c = json.loads(r['content'])
            for o in c.get('odds', []):
                o_row = o.copy()
                o_row['race_id'] = rid
                o_row['horse_num'] = str(o_row.get('horse_num', '')).zfill(2)
                odds.append(o_row)
    
    df_o = pd.DataFrame(odds)
    
    # Merge
    if not df_h.empty and not df_o.empty:
        df = pd.merge(df_h, df_o[['race_id', 'horse_num', 'odds_tan', 'pop_tan']], on=['race_id', 'horse_num'], how='left')
    elif not df_h.empty:
        # データが取れない場合のデモモード (開発・検証用)
        print("[WARN] オッズデータが見つからないため、検証用ダミーデータを生成します。")
        import numpy as np
        df = df_h.copy()
        # 単勝オッズ (1.0 - 50.0 相当の整数値)
        df['odds_tan'] = np.random.randint(10, 500, size=len(df))
        # 人気 (1 - 18)
        df['pop_tan'] = np.random.randint(1, 19, size=len(df))
    else:
        df = df_h
        
    return df

def feature_engineering(df):
    """特徴量エンジニアリングを行う"""
    if df.empty: return df
    
    # 型変換とスケーリング (10倍整数 -> 実数)
    df['odds_tan'] = pd.to_numeric(df['odds_tan'], errors='coerce') / 10.0
    df['pop_tan'] = pd.to_numeric(df['pop_tan'], errors='coerce')
    df['horse_num_int'] = pd.to_numeric(df['horse_num'], errors='coerce')
    
    # 独自指標: odds_per_pop
    df['odds_per_pop'] = df['odds_tan'] / df['pop_tan']
    
    # 欠損値補完
    df['odds_tan'] = df['odds_tan'].fillna(0)
    df['pop_tan'] = df['pop_tan'].fillna(99)
    df['odds_per_pop'] = df['odds_per_pop'].fillna(0)
    
    return df

def rule_base_predict(row):
    """ルールベースによる簡易予測ロジック (緩和版)"""
    # 条件: 単勝5倍以上100倍以下、かつ人気(1-10位)
    # これにより、パイプラインの貫通を優先的に確認する
    if 5.0 <= row['odds_tan'] <= 100.0 and row['pop_tan'] <= 10:
        return 1.0 # 推奨
    return 0.0

def run_inference(date_str):
    """メイン推論フロー"""
    df = fetch_data(date_str)
    if df.empty: return
    
    df = feature_engineering(df)
    
    model = load_prediction_model()
    
    if model:
        # モデルがある場合 (必須特徴量: odds_tan, pop_tan, odds_per_pop, horse_num_int)
        # ※ モデルの入力順序やカラム名に注意が必要だが、指示に従い上記4つを使用
        features = ['odds_tan', 'pop_tan', 'odds_per_pop', 'horse_num_int']
        X = df[features]
        try:
            df['pred_score'] = model.predict_proba(X)[:, 1] # クラス1の確率
            df['pred_mark'] = (df['pred_score'] > 0.5).astype(float)
        except Exception as e:
            print(f"[WARN] モデル推論中にエラーが発生しました。ルールベースに切り替えます: {e}")
            df['pred_mark'] = df.apply(rule_base_predict, axis=1)
            df['pred_score'] = df['pred_mark']
    else:
        # モデルがない場合
        df['pred_mark'] = df.apply(rule_base_predict, axis=1)
        df['pred_score'] = df['pred_mark']

    # デバッグ: 最初の5頭を無条件に表示
    print("\n--- DEBUG: TOP 5 HORSES LOADED ---")
    print(df[['race_id', 'horse_num', 'horse_name', 'odds_tan', 'pop_tan', 'odds_per_pop']].head(5))
    
    # 推奨馬 (マークあり、またはスコア上位) を表示
    recommended = df[df['pred_mark'] > 0].sort_values('pred_score', ascending=False)
    
    # 結果表示
    print("\n" + "="*80)
    print(f" AI PREDICTION RESULTS: {date_str}")
    print("="*80)
    
    # 推奨馬 (マークあり、またはスコア上位) を表示
    recommended = df[df['pred_mark'] > 0].sort_values('pred_score', ascending=False)
    
    if recommended.empty:
        print("推奨馬は見つかりませんでした。")
    else:
        # ヘッダー
        header = f"{'Race ID':<18} {'#':<2} {'Horse Name':<20} {'Odds':<5} {'Pop':<3} {'Score':<5}"
        print(header)
        print("-" * 80)
        for _, row in recommended.head(20).iterrows():
            name = str(row['horse_name'])
            # コンソール出力時のエンコーディングエラー対策
            safe_name = name.encode('cp932', errors='replace').decode('cp932')
            try:
                line = f"{row['race_id']:<18} {row['horse_num']:<2} {safe_name:<20} {row['odds_tan']:<5.1f} {int(row['pop_tan']):<3} {row['pred_score']:.3f}"
                print(line)
            except:
                print(f"{row['race_id']:<18} {row['horse_num']:<2} (Name Error) {row['odds_tan']:<5.1f} {int(row['pop_tan']):<3} {row['pred_score']:.3f}")

if __name__ == "__main__":
    # Windows用エンコーディング対策
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYYMMDD", default=None)
    args = parser.parse_args()
    
    target_date = args.date
    if not target_date:
        # デフォルトは明日 (現在時刻が 21:47 なので、明日のデータを想定)
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        target_date = tomorrow.strftime("%Y%m%d")
        
    run_inference(target_date)
