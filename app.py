
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
    Wraps a component function in a visual debug container using custom CSS and HTML.
    """
    # Custom CSS for the debug box
    css = f"""
    <style>
    .debug-box-{component_id} {{
        border: 2px dashed #ff4b4b;
        padding: 15px;
        margin-bottom: 20px;
        position: relative;
        border-radius: 5px;
    }}
    .debug-id-{component_id} {{
        position: absolute;
        top: -10px;
        right: 10px;
        background-color: #ff4b4b;
        color: white;
        padding: 2px 8px;
        font-size: 0.8em;
        font-weight: bold;
        border-radius: 3px;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    
    # Opening Wrapper
    st.markdown(f'<div class="debug-box-{component_id}"><div class="debug-id-{component_id}">ID: {component_id}</div>', unsafe_allow_html=True)
    
    # Title (Optional)
    if title:
        st.caption(f"🔧 {title}")

    # Execute the component content
    # We pass the return value back
    result = func(*args, **kwargs)
    
    # Closing Wrapper
    st.markdown('</div>', unsafe_allow_html=True)
    
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
    
    # Placeholder
    st.info("Waiting for race data...")
    st.caption("Detailed race cards will be rendered here.")

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
