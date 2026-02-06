import streamlit as st
import pandas as pd
import datetime
import os
import time
import threading
import sys
from dotenv import load_dotenv
from supabase import create_client

# Local Modules
try:
    from cloud_manager import CloudManager
    from worker_shopper import Shopper
    from worker_predictor_v4_1 import run_prediction_cycle
except ImportError as e:
    st.error(f"Module Import Error: {e}")
    st.stop()

# --- Config ---
st.set_page_config(page_title="Hybrid EV 2.0 Dashboard", layout="wide", page_icon="🏇")
load_dotenv()

# --- Database Connection ---
# 1. Try st.secrets (Streamlit Cloud)
# 2. Try os.getenv (Local .env)
def find_credentials():
    url, key = None, None
    try:
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets:
            key = st.secrets["SUPABASE_KEY"]
            
        if not url and "supabase" in st.secrets:
            section = st.secrets["supabase"]
            url = section.get("url") or section.get("URL") or section.get("SUPABASE_URL")
            key = section.get("key") or section.get("KEY") or section.get("SUPABASE_KEY")
    except:
        pass

    if not url: url = os.getenv("SUPABASE_URL")
    if not key: key = os.getenv("SUPABASE_KEY")
    return url, key

SUPABASE_URL, SUPABASE_KEY = find_credentials()

@st.cache_resource
def init_connection():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

supabase = init_connection()
if not supabase:
    st.error("🚨 Supabase Connection Failed. Check Secrets.")
    st.stop()

# --- Background Worker Manager ---
@st.cache_resource
def init_background_worker():
    # This runs exactly once due to cache_resource
    cm = CloudManager(supabase)
    shopper = Shopper(supabase)
    
    def background_loop():
        print("[BG] Worker Thread Started.")
        while True:
            try:
                # 1. Check Config
                is_active = cm.is_auto_bet_active()
                
                if is_active:
                    print("[BG] Auto Bet Active. Running cycle...")
                    # A. Run Prediction
                    run_prediction_cycle()
                    
                    # B. Run Shopper
                    # Note: daily_cap is checked inside shopper, but we should update it
                    current_cap = cm.get_daily_cap()
                    # We can pass limit to shopper or update env var logic in shopper
                    shopper.check_and_buy(daily_limit_override=current_cap)
                else:
                    print("[BG] Auto Bet INACTIVE. Sleeping...")
                
                time.sleep(60) # 1 min interval
            except Exception as e:
                print(f"[BG] Error: {e}")
                time.sleep(60)

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    return t

# Initialize Worker
init_background_worker()
cm = CloudManager(supabase)

# --- Sidebar: Fund Management (V4.1 Hybrid) ---
st.sidebar.title("🏇 V4.1 Hybrid Strategy")

# User Request: Selectable Unit Price (100, 1000, 10000)
unit_price = st.sidebar.selectbox("Base Unit Price (¥)", [100, 1000, 10000], index=0, help="初期投資ユニット額")
scale_factor = unit_price / 100

st.sidebar.info(
    f"""
    **Current Strategy**
    - **Single**: EV > 2.0 (Spear)
    - **Wide**: EV > 1.34 (Shield)
    - **Unit**: ¥{unit_price:,} (+Slide)
    """
)

# --- JRA Account & Admin Panel ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🏦 JRA Account & Control")

# Admin Auth
admin_pass_input = st.sidebar.text_input("Admin Password", type="password")
ADMIN_PASS_CORRECT = (admin_pass_input and admin_pass_input == os.getenv("ADMIN_PASS", "no_pass_set"))

# Status Display
is_active = cm.is_auto_bet_active()
status_icon = "🟢" if is_active else "🔴"
st.sidebar.metric("System Status", "ACTIVE" if is_active else "INACTIVE", delta=status_icon)

if ADMIN_PASS_CORRECT:
    st.sidebar.success("Unlocked")
    
    # Toggle
    new_active = st.sidebar.toggle("Enable Auto Bet", value=is_active)
    if new_active != is_active:
        cm.set_auto_bet_active(new_active)
        st.sidebar.rerun()
    
    # Cap Setting
    current_cap = cm.get_daily_cap()
    new_cap = st.sidebar.number_input("Daily Limit (¥)", value=current_cap, step=10000)
    if new_cap != current_cap:
        cm.set_daily_cap(int(new_cap))
        st.sidebar.caption("Limit updated.")
else:
    if admin_pass_input:
        st.sidebar.error("Invalid Password")
    else:
        st.sidebar.caption("🔒 Enter Password to Change Settings")

# --- Main Page Tabs ---
tab_live, tab_monitor, tab_compound = st.tabs(["📊 Live Dashboard", "🔍 Live Action Monitor", "📈 Compound Sim (2023-25)"])

with tab_live:
    # 1. Critical Alert System
    alert_active = False 
    if alert_active:
        st.error("🚨 CRITICAL: DATA MISMATCH - TRADING HALTED 🚨")
        st.stop()

    # 2. Key Metrics (Endurance Stats)
    st.markdown("### 📊 Live Performance (Endurance)")
    col1, col2, col3, col4 = st.columns(4)

    # Fetch Bets with Error Handling
    df_bets = pd.DataFrame()
    try:
        res_bets = supabase.table("bet_queue").select("*").execute()
        if res_bets.data:
            df_bets = pd.DataFrame(res_bets.data)
    except Exception as e:
        st.error(f"Error fetching bets: {e}")

    # Calculate Metrics
    today_invest = 0
    today_wins = 0
    
    if not df_bets.empty and 'created_at' in df_bets.columns:
        df_bets['created_at'] = pd.to_datetime(df_bets['created_at'])
        df_today = df_bets[df_bets['created_at'].dt.date == datetime.date.today()]
        today_invest = df_today[df_today['status'] == 'purchased']['amount'].sum() if 'amount' in df_today.columns else 0
        
    col1.metric("Current Streak (Loses)", "0", delta_color="inverse")
    col2.metric("Today's Invest", f"¥{today_invest:,}")
    col3.metric("Daily Cap", f"¥{cm.get_daily_cap():,}")
    col4.metric("Engine Status", "STANDBY" if not is_active else "RUNNING", delta_color="normal" if is_active else "off")

    # 3. Queue / EV Monitor
    st.subheader("🎯 Bet Queue & EV Analysis")
    if not df_bets.empty:
        df_bets = df_bets.sort_values('created_at', ascending=False)
        st.dataframe(
            df_bets[['created_at', 'race_id', 'horse_num', 'bet_type', 'status', 'details', 'amount']],
            use_container_width=True
        )
    else:
        st.info("No bets in queue yet.")

    # 4. Odds Monitor
    st.subheader("📈 Odds Monitor")
    try:
        res_raw = supabase.table("raw_race_data").select("*").order("created_at", desc=True).limit(5).execute()
        if res_raw.data:
            st.dataframe(pd.DataFrame(res_raw.data)[['created_at', 'data_type', 'race_id']])
        else:
            st.warning("No Data.")
    except:
        pass

with tab_monitor:
    st.header("🔍 Live Action Monitor")
    st.markdown("Real-time trading log and historical Trade/Pass decisions.")
    
    # Load Logs
    log_file = "trade_log_v4_1.csv"
    if os.path.exists(log_file):
        df_log = pd.read_csv(log_file)
        df_log['Date'] = pd.to_datetime(df_log['Date'])
        
        # Apply Scaling and Filters (Same as previous logic)
        if scale_factor != 1.0:
            df_log['Bet'] = df_log['Bet'] * scale_factor
            df_log['Payout'] = df_log['Payout'] * scale_factor
            df_log['Balance'] = df_log['Balance'] * scale_factor
        
        df_log['Year'] = df_log['Date'].dt.year
        df_log['Month'] = df_log['Date'].dt.month
        
        # --- Filters Interface ---
        f1, f2, f3 = st.columns(3)
        with f1:
            years = sorted(df_log['Year'].unique(), reverse=True)
            sel_y = st.multiselect("Year", years, default=years[:1])
            if sel_y: df_log = df_log[df_log['Year'].isin(sel_y)]
        
        # Display
        total_profit = df_log['Payout'].sum() - df_log['Bet'].sum()
        st.metric("Net Profit (Filtered)", f"¥{total_profit:,}")
        
        st.dataframe(df_log.sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.warning("No Trade Log found.")

with tab_compound:
    st.header("Compound Simulation")
    # ... (Keep existing simple logic or update later) ...
    st.info("V4.1 Simulation Comparison available in previous version.")
