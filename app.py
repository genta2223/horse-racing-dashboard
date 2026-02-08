
import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import json
from dotenv import load_dotenv
from supabase import create_client
import joblib
import sklearn
import numpy as np

MODEL_PATH = "local_engine/final_model.pkl"

# --- 0. Config & Setup ---
st.set_page_config(page_title="Racing Dashboard (Debug)", layout="wide")
load_dotenv()

# JST Timezone
jst = pytz.timezone('Asia/Tokyo')
now_jst = datetime.datetime.now(jst)

# Supabase Connection
@st.cache_resource
def init_connection():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    try:
        if url and key:
            return create_client(url, key)
    except:
        return None
    return None

supabase = init_connection()

# --- 1. Debug Container Wrapper ---
def debug_container(component_id, title, func, *args, **kwargs):
    marker_cls = f"debug-marker-{component_id}"
    css = f"""
    <style>
    div[data-testid="stVerticalBlock"]:has(div.{marker_cls}) {{
        border: 2px dashed #ff4b4b;
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 5px;
        position: relative;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    
    with st.container():
        st.markdown(f'''
            <div class="{marker_cls}" style="display:none;"></div>
            <div style="
                position: absolute;
                top: 0px;
                right: 0px;
                background-color: #ff4b4b;
                color: white;
                padding: 2px 8px;
                font-size: 0.8em;
                font-weight: bold;
                border-bottom-left-radius: 5px;
                z-index: 100;
            ">ID: {component_id}</div>
        ''', unsafe_allow_html=True)
        
        if title:
            st.caption(f"🔧 {title}")

        return func(*args, **kwargs)

# --- 2. Data Logic ---

@st.cache_data(ttl=60)
def fetch_todays_data(date_str):
    """Fetch 0B15 (SE7) and 0B30/31 (Odds) and merge using Pandas"""
    if not supabase: return pd.DataFrame(), pd.DataFrame(), {}
    try:
        # 1. Get 0B15 (Horse Info - SE7 from DB)
        res_h = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", date_str).execute()
        
        # 2. Get 0B30 or 0B31 (Odds)
        res_o = supabase.table("raw_race_data").select("race_id, content").in_("data_type", ["0B30", "0B31"]).eq("race_date", date_str).execute()
        
        # 3. Get 0B12 (Results)
        res_r = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B12").eq("race_date", date_str).execute()
        
        # 4. Get Prediction Results
        # race_id based filter (YYYYMMDD%)
        res_p = supabase.table("prediction_results").select("race_id, horse_num, predict_score, predict_flag").like("race_id", f"{date_str}%").execute()
        
        # --- Process Horses (0B15) ---
        horses_list = []
        parsed_races = []
        seen_races = set()
        
        place_map = {
            "01": "Sapporo", "02": "Hakodate", "03": "Fukushima", "04": "Niigata",
            "05": "Tokyo", "06": "Nakayama", "07": "Chukyo", "08": "Kyoto", 
            "09": "Hanshin", "10": "Kokura"
        }

        for r in (res_h.data if res_h.data else []):
            try:
                c = json.loads(r['content'])
                if c.get('record_type') == 'SE':
                    rid = c.get('race_id', '')
                    if not rid: continue
                    h_row = c.copy()
                    h_row['race_id'] = rid
                    h_row['horse_num'] = str(h_row.get('horse_num', '')).zfill(2)
                    horses_list.append(h_row)
                    
                    if rid not in seen_races:
                        jj = rid[8:10]
                        race_num = rid[14:16]
                        parsed_races.append({
                            "Race ID": rid,
                            "Place": place_map.get(jj, f"Jo{jj}"),
                            "Round": f"{int(race_num):02d}R",
                            "Date": date_str
                        })
                        seen_races.add(rid)
            except: continue

        df_horses = pd.DataFrame(horses_list)
        if not df_horses.empty:
            df_horses = df_horses.drop_duplicates(subset=['race_id', 'horse_num'], keep='last')
        
        # --- Process Odds (0B30/31) ---
        odds_list = []
        for r in (res_o.data if res_o.data else []):
            rid = r['race_id']
            try:
                c = json.loads(r['content'])
                for o in c.get('odds', []):
                    o_row = o.copy()
                    o_row['race_id'] = rid
                    o_row['horse_num'] = str(o_row.get('horse_num', '')).zfill(2)
                    odds_list.append(o_row)
            except: continue
        
        df_odds = pd.DataFrame(odds_list)
        if not df_odds.empty:
            df_odds = df_odds.drop_duplicates(subset=['race_id', 'horse_num'], keep='last')
            
        # --- Process Predictions ---
        df_pred = pd.DataFrame(res_p.data if res_p.data else [])
        if not df_pred.empty:
            df_pred['horse_num'] = df_pred['horse_num'].astype(str).str.zfill(2)
            df_pred = df_pred.drop_duplicates(subset=['race_id', 'horse_num'], keep='last')
        
        # --- Merge Phase (Pandas) ---
        if not df_horses.empty and not df_odds.empty:
            df_merged = pd.merge(df_horses, df_odds[['race_id', 'horse_num', 'odds_tan', 'pop_tan']], 
                                 on=['race_id', 'horse_num'], how='left')
        else:
            df_merged = df_horses
            if not df_merged.empty:
                df_merged['odds_tan'] = None
                df_merged['pop_tan'] = None
                
        # Merge Predictions if available
        if not df_merged.empty and not df_pred.empty:
            df_merged = pd.merge(df_merged, df_pred[['race_id', 'horse_num', 'predict_score', 'predict_flag']],
                                 on=['race_id', 'horse_num'], how='left')
            # Fill NaN
            df_merged['predict_score'] = df_merged['predict_score'].fillna(0.0)
            df_merged['predict_flag'] = df_merged['predict_flag'].fillna(0)
        elif not df_merged.empty:
             df_merged['predict_score'] = 0.0
             df_merged['predict_flag'] = 0
        
        # --- Process Results (Payoffs) ---
        parsed_payoffs = {}
        for r in (res_r.data if res_r.data else []):
            rid = r['race_id']
            try:
                c = json.loads(r['content'])
                if c.get('record_type') == 'HR':
                    if rid not in parsed_payoffs: parsed_payoffs[rid] = []
                    parsed_payoffs[rid].append(c)
            except: continue
            
        return pd.DataFrame(parsed_races), df_merged, parsed_payoffs
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), {}
@st.cache_resource
def load_prediction_model():
    """Load model once for the app session"""
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except:
            return None
    return None

def run_ai_prediction(df_race):
    """Run AI inference/Rule-base on a single race's dataframe"""
    if df_race.empty: return df_race
    
    df = df_race.copy()
    # 1. Feature Engineering (Simplified)
    df['odds_tan_val'] = pd.to_numeric(df['odds_tan'], errors='coerce') / 10.0
    df['pop_tan_val'] = pd.to_numeric(df['pop_tan'], errors='coerce')
    df['horse_num_int'] = pd.to_numeric(df['horse_num'], errors='coerce')
    df['odds_per_pop'] = df['odds_tan_val'] / (df['pop_tan_val'].replace(0, 99))
    
    # 2. Inference
    model = load_prediction_model()
    if model:
        # We know from worker_predict.py it expects 8 features, but we have 4.
        # So we use rule-base as fallback for now to ensure consistency.
        df['pred_score'] = 0.0
        df['pred_mark'] = 0.0
        
        # Rule-base fallback (Relaxed)
        mask = (df['odds_tan_val'] >= 5.0) & (df['odds_tan_val'] <= 100.0) & (df['pop_tan_val'] <= 10)
        df.loc[mask, 'pred_mark'] = 1.0
        
        # Calculate Score as Odds / Pop
        pops = df.loc[mask, 'pop_tan_val'].replace(0, 1)
        df.loc[mask, 'pred_score'] = df.loc[mask, 'odds_tan_val'] / pops
    else:
        df['pred_score'] = 0.0
        df['pred_mark'] = 0.0
        mask = (df['odds_tan_val'] >= 5.0) & (df['odds_tan_val'] <= 100.0) & (df['pop_tan_val'] <= 10)
        df.loc[mask, 'pred_mark'] = 1.0
        
        pops = df.loc[mask, 'pop_tan_val'].replace(0, 1)
        df.loc[mask, 'pred_score'] = df.loc[mask, 'odds_tan_val'] / pops
        
    return df

# --- 3. UI Components ---

def render_header():
    """ID: 001 Header Area"""
    cols = st.columns([2, 1, 1])
    with cols[0]:
        st.title(now_jst.strftime("%Y-%m-%d"))
    with cols[1]:
        st.metric("Current Time", now_jst.strftime("%H:%M:%S"))
    with cols[2]:
        status_color = "green" if supabase else "red"
        status_text = "Connected" if supabase else "Disconnected"
        st.markdown(f"**DB Status**: :{status_color}[{status_text}]")

def render_filter(available_places, available_columns):
    """ID: 003 Filter Area"""
    st.write("📍 **Race Filters & Display**")
    place_options = ["All"] + sorted(list(set([f"{p['Place']} ({p['Race ID'][8:10]})" for p in available_places])))
    c1, c2 = st.columns(2)
    with c1:
        sel_place = st.radio("Place:", place_options, horizontal=True)
    with c2:
        r_nums = ["All"] + [f"{i:02d}" for i in range(1, 13)]
        sel_num = st.radio("Race Num:", r_nums, horizontal=True)
    return {"place": sel_place, "race_num": sel_num}

def render_horse_list(rid, df_merged):
    """ID: 004 Merged Horse & Odds List"""
    # Extract place and race number from race ID (format: YYYYMMDDPPRRCCXX)
    # PP = place code (05=Tokyo, 06=Nakayama, etc.), RR = race number
    place_codes = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉"
    }
    
    if rid and len(rid) >= 12:
        place_code = rid[8:10]
        race_num = rid[10:12]
        place_name = place_codes.get(place_code, f"Place{place_code}")
        race_num_display = int(race_num) if race_num.isdigit() else race_num
        st.markdown(f"### 🏇 {place_name} {race_num_display}R")
    else:
        st.write(f"🏇 **Horse List: {rid}**")
    
    if df_merged.empty:
        st.info("No horse data found.")
        return

    df_race = df_merged[df_merged['race_id'] == rid].copy()
    if df_race.empty:
        st.warning(f"No horses found for Race ID: {rid}")
        return
    
    # Sort by horse_num (convert to int for proper numeric sorting)
    df_race['horse_num_int'] = pd.to_numeric(df_race['horse_num'], errors='coerce')
    df_race = df_race.sort_values('horse_num_int').drop(columns=['horse_num_int'])

    # Map columns to localized names
    sex_map = {"1": "牡", "2": "牝", "3": "セ"}
    def format_sex_age(row):
        sex = sex_map.get(str(row.get('sex_code')), '')
        try:
            age = int(row.get('age'))
        except:
            age = row.get('age', '')
        return f"{sex}{age}"
    df_race['SexAge'] = df_race.apply(format_sex_age, axis=1)
    
    col_map = {
        "waku": "枠",
        "horse_num": "番",
        "horse_name": "馬名",
        "SexAge": "性齢",
        "weight": "斤量",
        "jockey": "騎手",
        "odds_tan": "単勝",
        "pop_tan": "人気"
    }

    display_cols = [c for c in col_map.keys() if c in df_race.columns]
    df_display = df_race[display_cols].rename(columns=col_map)
    
    # Scale numeric odds (recorded as 10x integer often)
    if "単勝" in df_display.columns:
        df_display['単勝'] = pd.to_numeric(df_display['単勝'], errors='coerce') / 10.0
    if "人気" in df_display.columns:
        df_display['人気'] = pd.to_numeric(df_display['人気'], errors='coerce')
    # Format weight (recorded as 10x integer, e.g. 550 = 55.0 kg)
    if "斤量" in df_display.columns:
        df_display['斤量'] = pd.to_numeric(df_display['斤量'], errors='coerce') / 10.0

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "単勝": st.column_config.NumberColumn("単勝", format="%.1f", help="Win Odds"),
            "人気": st.column_config.NumberColumn("人気", format="%d"),
            "枠": st.column_config.TextColumn("枠", width="small"),
            "番": st.column_config.TextColumn("番", width="small"),
            "斤量": st.column_config.NumberColumn("斤量", format="%.1f kg"),
        }
    )

def render_payoff_data(selected_rid, payoffs_map):
    """New Component: Results (HR Records)"""
    st.markdown("---")
    with st.expander("📊 **Race Results (Payoff Data)**", expanded=False):
        if not selected_rid:
            st.write("No race selected.")
            return
        if selected_rid in payoffs_map:
            st.dataframe(pd.DataFrame(payoffs_map[selected_rid]), use_container_width=True)
        else:
            st.write(f"No payoff (HR) records found for {selected_rid}.")

# --- 4. Main Layout ---

@st.cache_data(ttl=60)
def fetch_available_dates():
    """Fetch distinct race_dates from raw_race_data (0B15)"""
    if not supabase: return []
    try:
        # Limit to 100 recent entries to find dates
        res = supabase.table("raw_race_data").select("race_date").eq("data_type", "0B15").order("race_date", desc=True).limit(200).execute()
        if res.data:
            # Extract unique dates and sort descending
            dates = sorted(list(set([r['race_date'] for r in res.data])), reverse=True)
            return dates
    except Exception as e:
        print(f"Date Fetch Error: {e}")
    return []

def render_date_selector(available_dates):
    """ID: 002 Date Selector"""
    st.write("📅 **Date Selection**")
    
    if not available_dates:
        st.warning("No data found in DB.")
        # Fallback to today if no data
        return now_jst.strftime("%Y%m%d")
    
    # Default selection logic:
    # 1. Today
    # 2. Closest future date
    # 3. Newest past date (index 0)
    today_str = now_jst.strftime("%Y%m%d")
    default_ix = 0
    
    if today_str in available_dates:
        default_ix = available_dates.index(today_str)
    
    selected_date = st.selectbox("Select Date:", available_dates, index=default_ix, key="main_date_selector")
    return selected_date

# --- 4. Main Layout ---

def main():
    # Sidebar: System Status Only
    with st.sidebar:
        st.header("System Status")
        st.write("Mode: Gatekeeper Validated")
        st.write(f"Server Time: {now_jst.strftime('%Y-%m-%d %H:%M')}")
        
        status_color = "green" if supabase else "red"
        status_text = "Online" if supabase else "Offline"
        st.markdown(f"**DB Connection**: :{status_color}[{status_text}]")
        
        if st.button("Clear Cache"):
            st.cache_data.clear()
            st.rerun()

    # Main Area
    debug_container("001", "Header Area", render_header)
    
    # 1. Date Selection
    available_dates = fetch_available_dates()
    
    # Layout for filters: Date | Place | RaceNum
    st.markdown("---")
    c_date, c_place, c_num = st.columns([1, 1, 1])
    
    with c_date:
        date_str = render_date_selector(available_dates)
        
    # Fetch Data for selected date
    df_races, df_merged, todays_payoffs = fetch_todays_data(date_str)
    
    if df_races.empty:
        st.warning(f"No race data found for {date_str}.")
        return

    # 2. Place & RaceNum Filters
    # Calculate available options properly
    place_options = ["All"] + sorted(list(set([f"{p['Place']} ({p['Race ID'][8:10]})" for p in df_races.to_dict('records')])))
    
    with c_place:
        st.write("📍 **Place**")
        sel_place = st.selectbox("Select Place:", place_options, key="filter_place")
        
    with c_num:
        st.write("🏁 **Race Num**")
        r_nums = ["All"] + [f"{i:02d}" for i in range(1, 13)]
        sel_num = st.selectbox("Select Race:", r_nums, key="filter_race")

    filters = {"place": sel_place, "race_num": sel_num}
    
    # Apply Filters
    filtered_races = df_races.copy()
    if filters.get("place") != "All":
        code = filters['place'].split("(")[-1].replace(")", "")
        filtered_races = filtered_races[filtered_races['Race ID'].str.slice(8,10) == code]
    
    if filters.get("race_num") != "All":
        num = filters['race_num']
        filtered_races = filtered_races[filtered_races['Race ID'].str.slice(14,16) == num]

    # Tabs
    tab1, tab2 = st.tabs(["📋 Dashboard", "🤖 AI予測"])
    
    with tab1:
        st.write(f"### 🏁 Race List ({date_str})")
        
        if not filtered_races.empty:
            st.dataframe(filtered_races, use_container_width=True, hide_index=True)
            
            # Race Detail Selector (within filtered)
            race_options_dash = [f"{r['Place']} {r['Round']} ({r['Race ID']})" for _, r in filtered_races.iterrows()]
            selected_option_dash = st.selectbox("View details for:", race_options_dash, key="rid_dash_sel")
            selected_rid = selected_option_dash.split("(")[-1].replace(")", "")
            
            debug_container("004", "Merged Horse/Odds List", render_horse_list, selected_rid, df_merged)
            render_payoff_data(selected_rid, todays_payoffs)
        else:
            st.warning("No races match the selected filters.")
            
    with tab2:
        st.header(f"AI Prediction Mode ({date_str})")
        if filtered_races.empty:
             st.warning("No races found matching filters.")
        else:
            # AI Tab also respects filters
            race_options = []
            for _, row in filtered_races.iterrows():
                rid = row['Race ID']
                place = row.get('Place', rid[8:10])
                race_num = row.get('Round', f"{int(rid[14:16])}R")
                race_options.append(f"{place} {race_num} ({rid})")
            
            selected_option = st.selectbox("Select Race for AI Analysis:", race_options, key="rid_ai")
            selected_rid_ai = selected_option.split("(")[-1].replace(")", "")
            
            df_curr = df_merged[df_merged['race_id'] == selected_rid_ai].copy()
            
            # ... (Existing logic for prediction display) ...
            if df_curr['odds_tan'].isna().all() and 'predict_score' not in df_curr.columns:
                 # Check if we have prediction results even if odds are missing? 
                 # Usually odds come with prediction.
                 pass

            if df_curr['odds_tan'].isna().all():
                 # Allow demo if button clicked (only if no prediction result exists)
                 if 'predict_score' in df_curr.columns and (df_curr['predict_score'] > 0).any():
                     pass # We have scores, so proceed
                 else:
                    st.warning("⚠️ オッズデータが不足しているため、正確な予測ができません。ダミーデータでテストしますか？")
                    if st.button("Generate Test Odds"):
                        df_curr['odds_tan'] = np.random.randint(50, 500, size=len(df_curr))
                        df_curr['pop_tan'] = np.random.randint(1, 15, size=len(df_curr))
                    else:
                        st.stop()
            
            # Use stored prediction if available
            if 'predict_score' in df_curr.columns and (df_curr['predict_score'] > 0).any():
                df_pred = df_curr.copy()
                df_pred['pred_score'] = df_pred['predict_score']
                df_pred['pred_mark'] = df_pred.get('predict_flag', 0)
                # Validation cols
                df_pred['odds_tan_val'] = pd.to_numeric(df_pred['odds_tan'], errors='coerce') / 10.0
                df_pred['pop_tan_val'] = pd.to_numeric(df_pred['pop_tan'], errors='coerce')
                st.info("💡 保存済みの予測データを表示しています")
            else:
                # Fallback
                st.warning("⚠️ 保存された予測データがないため、簡易ルールベースで計算します")
                df_pred = run_ai_prediction(df_curr)

            # Sort and Display
            rec = df_pred.sort_values('pred_score', ascending=False)
            
            if rec.empty:
                st.info("表示するデータがありません。")
            else:
                place_map = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
                             "05": "東京", "06": "中山", "07": "中京", "08": "京都", 
                             "09": "阪神", "10": "小倉"}
                jj = selected_rid_ai[8:10]
                race_num = int(selected_rid_ai[14:16])
                place_name = place_map.get(jj, f"場{jj}")
                
                rec = rec.copy()
                rec['場所'] = place_name
                rec['R'] = f"{race_num}R"
                rec['単勝'] = rec['odds_tan_val']
                rec['人気'] = rec['pop_tan_val']
                rec['AIスコア'] = rec['pred_score']
                
                def highlight_high_score(val):
                    color = 'font-weight: bold;' if val >= 2.0 else ''
                    return color

                st.subheader(f"📍 {place_name} {race_num}R 予測結果")
                st.dataframe(
                    rec[['場所', 'R', 'horse_num', 'horse_name', '単勝', '人気', 'AIスコア', 'pred_mark']]
                    .style
                    .background_gradient(subset=['AIスコア'], cmap='YlOrRd', vmin=0, vmax=5)
                    .format({"単勝": "{:.1f}", "AIスコア": "{:.3f}", "人気": "{:.0f}"})
                    .applymap(highlight_high_score, subset=['AIスコア']),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "horse_num": st.column_config.TextColumn("番"),
                        "horse_name": st.column_config.TextColumn("馬名"),
                        "pred_mark": st.column_config.NumberColumn("Mark", format="%d")
                    }
                )

if __name__ == "__main__":
    main()
