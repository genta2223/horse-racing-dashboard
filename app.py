
import streamlit as st
import pandas as pd
import datetime
import pytz
import os
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
    """
    Wraps a component function in a visual debug container using st.container and CSS :has().
    """
    # Define the unique marker class
    marker_cls = f"debug-marker-{component_id}"
    
    # CSS to style the PARENT container of the marker
    css = f"""
    <style>
    div[data-testid="stVerticalBlock"]:has(div.{marker_cls}) {{
        border: 2px dashed #ff4b4b;
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 5px;
        position: relative;
    }}
    /* Badge styling using pseudo-element or separate div? 
       Let's try absolute positioning a real div inside */
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    
    with st.container():
        # Inject marker and badge
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
        
        # Title (Optional)
        if title:
            st.caption(f"🔧 {title}")

        # Execute component
        result = func(*args, **kwargs)
        
        return result

# --- 2. Components ---

@st.cache_data(ttl=60)
def fetch_todays_data(date_str):
    if not supabase: return [], {}
    try:
        # 1. Get 0B15 (Schedule/Horse Info)
        res_h = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", date_str).order("race_id").execute()
        
        # 2. Get 0B30/31 (Odds)
        res_o = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B31").eq("race_date", date_str).execute()
        
        # 3. Get 0B12 (Results)
        res_r = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B12").eq("race_date", date_str).execute()
        
        raw_horses = res_h.data if res_h.data else []
        raw_odds = res_o.data if res_o.data else []
        raw_results = res_r.data if res_r.data else []
        
        parsed_races = []
        parsed_horses = {} # Key: race_id, Value: dict of horse dicts
        
        # Maps for Results and Odds
        import json
        results_map = {r['race_id']: json.loads(r['content']) for r in raw_results}
        odds_map = {r['race_id']: json.loads(r['content']) for r in raw_odds}

        place_map = {
            "01": "Sapporo", "02": "Hakodate", "03": "Fukushima", "04": "Niigata",
            "05": "Tokyo", "06": "Nakayama", "07": "Chukyo", "08": "Kyoto", 
            "09": "Hanshin", "10": "Kokura"
        }
        
        # Process 0B15 (Primary Source for Race List)
        seen_races = set()

        for r in raw_horses:
            rid = r['race_id']
            if not rid.startswith("20") or len(rid) < 14: continue 
            
            try:
                content_json = json.loads(r['content'])
                rtype = content_json.get('record_type', 'SE')
                
                # --- RA: Race Header ---
                if rtype == 'RA' or 'race_id' in content_json:
                    if rid not in seen_races:
                        jj = rid[8:10]
                        race_num_val = int(rid[14:16])
                        
                        race_info = {
                            "Race ID": rid,
                            "Place": place_map.get(jj, f"Jo{jj}"),
                            "Round": f"{race_num_val:02d}R",
                            "Type": "0B15"
                        }
                        # Add Result Info if exists
                        if rid in results_map:
                            race_info["Winner"] = results_map[rid].get("rank_1_horse", "--")
                            race_info["Payout"] = results_map[rid].get("pay_tan", 0)
                            
                        parsed_races.append(race_info)
                        seen_races.add(rid)
                        
                # --- SE: Horse Data ---
                if 'horse_num' in content_json or rtype == 'SE':
                    if rid not in parsed_horses:
                        parsed_horses[rid] = {}
                    
                    horse_data = content_json.copy()
                    horse_data['Race ID'] = rid
                    
                    # Align keys for display
                    umaban = str(horse_data.get('horse_num', horse_data.get('Umaban', '')))
                    horse_data['Umaban'] = umaban
                    horse_data['Horse'] = horse_data.get('horse_name', horse_data.get('Horse', ''))
                    horse_data['Jockey'] = horse_data.get('jockey', horse_data.get('Jockey', ''))
                    
                    # Add Odds Info if exists
                    if rid in odds_map:
                        odds_list = odds_map[rid].get("odds", [])
                        for o in odds_list:
                            if str(o.get("horse_num")) == umaban:
                                horse_data["Odds"] = o.get("odds_tan", "--")
                                break
                    
                    if umaban:
                        parsed_horses[rid][umaban] = horse_data
                        
            except:
                import traceback
                st.code(traceback.format_exc())
                continue
        
        # Convert parsed_horses dict-of-dicts to dict-of-lists
        final_horses = {k: sorted(list(v.values()), key=lambda x: x.get('Umaban', '99')) for k, v in parsed_horses.items()}
            
        return parsed_races, final_horses
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        import traceback
        st.code(traceback.format_exc())
        return [], {}

# --- 2. Components ---

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
    
    # 1. Place Filter (Dynamic)
    place_options = ["All"] + sorted(list(set([f"{p['Place']} ({p['Race ID'][8:10]})" for p in available_places])))
    
    c1, c2 = st.columns(2)
    with c1:
        sel_place = st.radio("Place:", place_options, horizontal=True)
    
    with c2:
        # 2. Race Number Filter
        r_nums = ["All"] + [f"{i:02d}" for i in range(1, 13)]
        sel_num = st.radio("Race Num:", r_nums, horizontal=True)

    st.markdown("---")
    # 3. Column Selector
    st.write("👀 **Column Visibility**")
    # Default: ID, Place, Round
    default_cols = ["Place", "Round", "Race ID"]
    sel_cols = st.multiselect("Select columns:", available_columns, default=default_cols)
    
    return {"place": sel_place, "race_num": sel_num, "columns": sel_cols}

def render_race_list(data, filters):
    """ID: 002 Race List Area"""
    sel_place = filters['place']
    sel_num = filters['race_num']
    sel_cols = filters['columns']
    
    st.write(f"📋 **Race List** ({len(data)} potential races)")
    
    if not data:
        st.info("No race data found for today.")
        return [] # Return empty list of filtered RIDs

    # Apply Filters
    filtered = []
    for r in data:
        # Place Filter
        if sel_place != "All":
            code_in_opt = sel_place.split("(")[-1].replace(")", "")
            if r['Race ID'][8:10] != code_in_opt: continue
            
        # Num Filter
        if sel_num != "All":
            if r['Round'] != f"{sel_num}R": continue
            
        filtered.append(r)
    
    if filtered:
        # Display Only Selected Columns
        df = pd.DataFrame(filtered)
        valid_cols = [c for c in sel_cols if c in df.columns]
        if valid_cols:
            st.dataframe(df[valid_cols], use_container_width=True)
        else:
            st.warning("No columns selected.")
            
        return [r['Race ID'] for r in filtered]
    else:
        st.warning("No races match the selected filters.")
        return []

def render_horse_list(filtered_rids, horses_map):
    """ID: 004 Horse List"""
    st.write(f"🏇 **Horse List** (Targeting {len(filtered_rids)} Races)")
    
    if not filtered_rids:
        st.info("No races selected.")
        return

    # Aggregate horses
    all_horses = []
    for rid in filtered_rids:
        if rid in horses_map:
            all_horses.extend(horses_map[rid])
            
    if all_horses:
        st.write(f"Found {len(all_horses)} horses.")
        df = pd.DataFrame(all_horses)
        # Display all columns (as requested)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No horse (SE) data found for the selected races.")


# --- 3. Main Layout ---

def main():
    # Sidebar
    with st.sidebar:
        st.header("Debug Console")
        st.write("Mode: Visual Debugger")
    
    # Global Data Fetch
    date_str = now_jst.strftime("%Y%m%d")
    todays_data, todays_horses = fetch_todays_data(date_str)
    
    # Extract all possible keys for column selector
    all_keys = list(todays_data[0].keys()) if todays_data else ["Race ID", "Place", "Round"]
    
    # Component 001: Header
    debug_container("001", "Header Area", render_header)
    
    # Component 003: Filter (Pass available places & columns)
    filters = debug_container("003", "Filter Area", render_filter, todays_data, all_keys)
    
    # Component 002: Race List (Returns filtered RIDs)
    filtered_rids = debug_container("002", "Race List Area", render_race_list, todays_data, filters)
    
    # Component 004: Horse List
    if filtered_rids is not None:
        debug_container("004", "Horse List", render_horse_list, filtered_rids, todays_horses)

if __name__ == "__main__":
    main()
