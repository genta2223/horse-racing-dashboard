
import streamlit as st
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

# --- 1.5 Data Fetching & Processing ---
@st.cache_data(ttl=60)
def fetch_todays_data(date_str):
    if not supabase: return []
    try:
        # Get 0B15 (Schedule)
        res = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", date_str).order("race_id").execute()
        races = res.data if res.data else []
        
        parsed_data = []
        place_map = {
            "01": "Sapporo", "02": "Hakodate", "03": "Fukushima", "04": "Niigata",
            "05": "Tokyo", "06": "Nakayama", "07": "Chukyo", "08": "Kyoto", 
            "09": "Hanshin", "10": "Kokura"
        }

        for r in races:
            rid = r['race_id']
            if not rid.startswith("20"): continue 
            
            # ID Format: YYYYMMDDJJRR (12 digits) or longer
            # JJ = 8:10, RR = 10:12
            jj = rid[8:10]
            rr = rid[10:12]
            
            parsed_data.append({
                "race_id": rid,
                "place_code": jj,
                "place_name": place_map.get(jj, f"Unknown({jj})"),
                "race_num": rr,
                "raw": r['content']
            })
            
        return parsed_data
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return []

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

def render_filter(available_places):
    """ID: 003 Filter Area"""
    st.write("📍 **Race Filters**")
    
    # 1. Place Filter (Dynamic)
    # create options like ["All", "Tokyo (05)", "Kyoto (08)"]
    place_options = ["All"] + sorted(list(set([f"{p['place_name']} ({p['place_code']})" for p in available_places])))
    
    c1, c2 = st.columns(2)
    with c1:
        sel_place = st.radio("Place:", place_options, horizontal=True)
    
    with c2:
        # 2. Race Number Filter
        # 1-12
        r_nums = ["All"] + [f"{i:02d}" for i in range(1, 13)]
        sel_num = st.radio("Race Num:", r_nums, horizontal=True)
        
    return {"place": sel_place, "race_num": sel_num}

def render_race_list(data, filters):
    """ID: 002 Race List Area"""
    sel_place = filters['place']
    sel_num = filters['race_num']
    
    st.write(f"📋 **Race List** (Filter: `{sel_place}` / `{sel_num}`R)")
    
    if not data:
        st.info("No race data found for today.")
        return

    # Apply Filters
    filtered = []
    for r in data:
        # Place Filter
        if sel_place != "All":
            # sel_place format: "Name (Code)" e.g. "Tokyo (05)"
            # Check if code maps
            code_in_opt = sel_place.split("(")[-1].replace(")", "")
            if r['place_code'] != code_in_opt: continue
            
        # Num Filter
        if sel_num != "All":
            if r['race_num'] != sel_num: continue
            
        filtered.append(r)
    
    if filtered:
        # Display as clean dataframe
        display_data = [{
            "Time": "Unknown", # Needs parsing from content if possible, or just ID
            "Place": d['place_name'],
            "Race": f"{d['race_num']}R",
            "ID": d['race_id'],
        } for d in filtered]
        
        st.dataframe(display_data, use_container_width=True)
    else:
        st.warning("No races match the selected filters.")

# --- 3. Main Layout ---

def main():
    with st.sidebar:
        st.header("Debug Console")
        st.write("Mode: Visual Debugger")
    
    # Global Data Fetch
    date_str = now_jst.strftime("%Y%m%d")
    todays_data = fetch_todays_data(date_str)
    
    # Component 001: Header
    debug_container("001", "Header Area", render_header)
    
    # Component 003: Filter (Pass available places for dynamic options)
    filters = debug_container("003", "Filter Area", render_filter, todays_data)
    
    # Component 002: Race List (Pass filtered data)
    debug_container("002", "Race List Area", render_race_list, todays_data, filters)

if __name__ == "__main__":
    main()
