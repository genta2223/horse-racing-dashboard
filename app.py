
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

def render_filter():
    """ID: 003 Filter Area"""
    st.write("📍 **Place Filter**")
    # Horizontal Radio
    selection = st.radio(
        "Select Place:",
        ["All", "Tokyo (05)", "Kyoto (08)", "Kokura (10)"],
        horizontal=True,
        label_visibility="collapsed"
    )
    return selection

def render_race_list(filter_selection):
    """ID: 002 Race List Area"""
    st.write(f"📋 **Race List** (Filter: `{filter_selection}`)")
    
    # Fetch Data
    date_str = now_jst.strftime("%Y%m%d")
    if not supabase:
        st.error("DB Not Connected")
        return

    try:
        # Get 0B15 (Schedule/Race Info)
        res = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", date_str).order("race_id").execute()
        races = res.data if res.data else []
        
        if not races:
            st.warning(f"No 0B15 data found for {date_str}.")
            return
            
        # Process Data
        valid_races = []
        for r in races:
            rid = r['race_id']
            if not rid.startswith("20"): continue # Skip garbage
            
            # Simple Place Parsing from ID (YYYYMMDDJJRR)
            # JJ is 8:10
            jj = rid[8:10]
            
            # Filter Logic
            if filter_selection == "Tokyo (05)" and jj != "05": continue
            if filter_selection == "Kyoto (08)" and jj != "08": continue
            if filter_selection == "Kokura (10)" and jj != "10": continue
            
            valid_races.append({
                "Race ID": rid,
                "Place Code": jj,
                "Race Num": rid[10:12] if len(rid) >= 12 else "??",
                "Raw Content (Partial)": r['content'][:50] + "..." if r['content'] else ""
            })
            
        if valid_races:
            st.dataframe(valid_races, use_container_width=True)
        else:
            st.info("No races match the filter.")

    except Exception as e:
        st.error(f"Error fetching data: {e}")

# --- 3. Main Layout ---

def main():
    # Sidebar (Just basic config for now)
    with st.sidebar:
        st.header("Debug Console")
        st.write("Mode: Visual Debugger")
    
    # Component 001: Header
    debug_container("001", "Header Area", render_header)
    
    # Component 003: Filter
    # Need to capture return value
    selected_place = debug_container("003", "Filter Area", render_filter)
    
    # Component 002: Race List
    # Pass data from 003 to 002
    debug_container("002", "Race List Area", render_race_list, selected_place)

if __name__ == "__main__":
    main()
