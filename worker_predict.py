
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
    # Deduplicate db_h: Keep last entry for each (race_id, horse_num)
    # Assuming the API returns data in vague insertion order, but explicit sort by something would be better if available.
    # Since we can't easily sort by created_at here without adding it to the list, we assume the list 'horses' 
    # reflects the fetch order. Typically Supabase returns oldest first or newest first. 
    # Let's trust insertion order for now and keep 'last'.
    if not df_h.empty:
        df_h = df_h.drop_duplicates(subset=['race_id', 'horse_num'], keep='last')
    
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
    # Deduplicate df_o
    if not df_o.empty:
        df_o = df_o.drop_duplicates(subset=['race_id', 'horse_num'], keep='last')
    
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

def rule_base_predict_score(row):
    """ルールベーススコア計算 (Odds / Pop)"""
    try:
        odds = float(row.get('odds_tan', 0))
        pop = float(row.get('pop_tan', 99))
        if pop <= 0.1: pop = 1.0 # Avoid zero division
        return odds / pop
    except:
        return 0.0

def rule_base_predict_mark(row):
    """ルールベース買い目フラグ"""
    # 条件: 単勝5倍以上100倍以下、かつ人気(1-10位)
    try:
        odds = float(row.get('odds_tan', 0))
        pop = float(row.get('pop_tan', 99))
        if 5.0 <= odds <= 100.0 and pop <= 10:
            return 1.0
    except:
        pass
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
            # 特徴量数の不一致などが発生する可能性があるためtry-except
            # LightGBMの場合、特徴量数が違うとFatalになるが、Python側でキャッチできない場合もある。
            # 事前にチェックする
            if hasattr(model, 'n_features_') and model.n_features_ != len(features):
                raise ValueError(f"Model expects {model.n_features_} features, but got {len(features)}")
            
            df['pred_score'] = model.predict_proba(X)[:, 1] # クラス1の確率
            df['pred_mark'] = (df['pred_score'] > 0.5).astype(float)
        except Exception as e:
            print(f"[WARN] モデル推論中にエラーが発生しました。ルールベースに切り替えます: {e}")
            df['pred_score'] = df.apply(rule_base_predict_score, axis=1)
            df['pred_mark'] = df.apply(rule_base_predict_mark, axis=1)
    else:
        # モデルがない場合
        df['pred_score'] = df.apply(rule_base_predict_score, axis=1)
        df['pred_mark'] = df.apply(rule_base_predict_mark, axis=1)

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
    recommended = df[df['pred_score'] > 0].sort_values('pred_score', ascending=False)
    
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

    # --- DB 保存処理 ---
    print("\n[INFO] Saving prediction results to Supabase...")
    save_prediction_results(df)

def save_prediction_results(df):
    """予測結果を prediction_results テーブルに保存する"""
    if df.empty: return

    # 保存用リスト作成
    payload = []
    now_iso = datetime.datetime.now().isoformat()
    
    for _, row in df.iterrows():
        # スコアが0のものは保存しない（または全頭保存するか？ユーザー要望は特に指定なしだが、容量節約のため0以外、あるいは全頭）
        # ヒートマップ表示のためには全頭保存した方が良い（「低い」ことも情報）。
        # ここでは全頭保存する。
        
        # float型に変換し、None/NaNを処理
        score = row.get('pred_score', 0.0)
        if pd.isna(score): score = 0.0
        
        p_mark = int(row.get('pred_mark', 0))
        
        item = {
            "race_id": str(row['race_id']),
            "horse_num": str(row['horse_num']),
            "predict_score": round(float(score), 3), # 小数点第3位まで保持
            "predict_flag": p_mark,
            "created_at": now_iso
        }
        payload.append(item)
    
    if not payload:
        return

    # SupabaseへUpsert (一括)
    # 実際にはデータ量が多いと分割が必要だが、1日分なら数千件なので分割推奨
    batch_size = 500
    total_saved = 0
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    rest_url = f"{url}/rest/v1/prediction_results"
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates" # upsert based on primary key (race_id, horse_num)
    }

    for i in range(0, len(payload), batch_size):
        batch = payload[i:i+batch_size]
        try:
            resp = requests.post(rest_url, headers=headers, json=batch)
            if resp.status_code in (200, 201, 204):
                total_saved += len(batch)
            else:
                print(f"[ERROR] Save failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[ERROR] Save request error: {e}")
            
    print(f"[INFO] Saved {total_saved} prediction records.")

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
        # カレンダー通り翌日、または当日夜なら翌日
        tomorrow = now + datetime.timedelta(days=1)
        target_date = tomorrow.strftime("%Y%m%d")
        
    run_inference(target_date)
