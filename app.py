
import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import json
from dotenv import load_dotenv
from supabase import create_client

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
        # 1. Get 0B15 (Horse Info)
        res_h = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", date_str).execute()
        
        # 2. Get 0B30 or 0B31 (Odds)
        res_o = supabase.table("raw_race_data").select("race_id, content").in_("data_type", ["0B30", "0B31"]).eq("race_date", date_str).execute()
        
        # 3. Get 0B12 (Results)
        res_r = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B12").eq("race_date", date_str).execute()
        
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
            rid = r['race_id']
            try:
                c = json.loads(r['content'])
                if c.get('record_type') == 'SE':
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
                            "Round": f"{int(race_num):02d}R"
                        })
                        seen_races.add(rid)
            except: continue

        df_horses = pd.DataFrame(horses_list)
        
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
        
        # --- Merge Phase (Pandas) ---
        if not df_horses.empty and not df_odds.empty:
            df_merged = pd.merge(df_horses, df_odds[['race_id', 'horse_num', 'odds_tan', 'pop_tan']], 
                                 on=['race_id', 'horse_num'], how='left')
        else:
            df_merged = df_horses
            if not df_merged.empty:
                df_merged['odds_tan'] = None
                df_merged['pop_tan'] = None
        
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
    st.write(f"🏇 **Horse List: {rid}**")
    if df_merged.empty:
        st.info("No horse data found.")
        return

    df_race = df_merged[df_merged['race_id'] == rid].copy()
    if df_race.empty:
        st.warning(f"No horses found for Race ID: {rid}")
        return

    # Map columns
    sex_map = {"1": "牡", "2": "牝", "3": "セ"}
    df_race['SexAge'] = df_race.apply(lambda r: f"{sex_map.get(str(r.get('sex_code')), '')}{r.get('age', '')}", axis=1)
    
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
    
    if "単勝" in df_display.columns:
        df_display['単勝'] = pd.to_numeric(df_display['単勝'], errors='coerce') / 10.0
    if "人気" in df_display.columns:
        df_display['人気'] = pd.to_numeric(df_display['人気'], errors='coerce')

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "単勝": st.column_config.NumberColumn("単勝", format="%.1f"),
            "人気": st.column_config.NumberColumn("人気", format="%d"),
            "枠": st.column_config.TextColumn("枠", width="small"),
            "番": st.column_config.TextColumn("番", width="small"),
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

def main():
    with st.sidebar:
        st.header("Debug Console")
        st.write("Mode: Gatekeeper Validated")
        st.write(f"Current Time: {now_jst.strftime('%Y-%m-%d %H:%M:%S')}")
    
    date_str = now_jst.strftime("%Y%m%d")
    df_races, df_merged, todays_payoffs = fetch_todays_data(date_str)
    
    if df_races.empty:
        st.warning(f"No race data found for {date_str}.")
        return

    debug_container("001", "Header Area", render_header)
    filters = debug_container("003", "Filter Area", render_filter, df_races.to_dict('records'), list(df_races.columns))
    
    st.write("### 🏁 Select a Race")
    filtered_races = df_races.copy()
    if filters.get("place") != "All":
        code = filters['place'].split("(")[-1].replace(")", "")
        filtered_races = filtered_races[filtered_races['Race ID'].str.slice(8,10) == code]
    
    if not filtered_races.empty:
        st.dataframe(filtered_races, use_container_width=True, hide_index=True)
        selected_rid = st.selectbox("View details for Race ID:", filtered_races['Race ID'].tolist())
        
        debug_container("004", "Merged Horse/Odds List", render_horse_list, selected_rid, df_merged)
        render_payoff_data(selected_rid, todays_payoffs)
    else:
        st.warning("No races match the selected filters.")

if __name__ == "__main__":
    main()
