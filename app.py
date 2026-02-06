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
def find_credentials() -> tuple[str | None, str | None]:  # FIX #11: Type hints
    """Find Supabase credentials from secrets or environment"""
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
    """Initialize Supabase connection"""
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
    """
    FIX #3: Return shared instances to prevent duplication
    Initialize background worker thread with shared CloudManager and Shopper instances
    """
    cm = CloudManager(supabase)
    shopper = Shopper(supabase)
    
    def background_loop():
        print("[BG] Worker Thread Started.")
        while True:
            try:
                # Check if auto-bet is active
                is_active = cm.is_auto_bet_active()
                
                if is_active:
                    print("[BG] Auto Bet Active. Running cycle...")
                    
                    # A. Run Prediction (with error handling)
                    try:
                        run_prediction_cycle()
                    except Exception as e:
                        print(f"[BG] Prediction Error: {e}")
                        cm.log_system_event("ERROR", "Prediction Failed", str(e))
                    
                    # B. Run Shopper (with enhanced error handling)
                    current_cap = cm.get_daily_cap()
                    try:
                        shopper.check_and_buy(daily_limit_override=current_cap)
                    except Exception as e:
                        print(f"[BG] Shopper Critical Error: {e}")
                        cm.log_system_event("CRITICAL", "Shopper Crashed", str(e))
                        # FIX #6: Wrap alert sending to prevent cascading failures
                        try:
                            shopper.send_error_alert(e, context="Shopper Loop")
                        except Exception as alert_error:
                            print(f"[BG] Alert sending failed: {alert_error}")
                            cm.log_system_event("CRITICAL", "Alert System Failed", str(alert_error))
                else:
                    print("[BG] Auto Bet INACTIVE. Sleeping...")
                
                time.sleep(60)  # 1 min interval
                
            except Exception as e:
                print(f"[BG] Global Loop Error: {e}")
                try:
                    cm.log_system_event("CRITICAL", "Global Loop Crashed", str(e))
                except:
                    print("[BG] Even logging failed. System in critical state.")
                time.sleep(60)

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    
    # FIX #3: Return all shared resources
    return {
        "thread": t,
        "cloud_manager": cm,
        "shopper": shopper
    }

# Initialize Worker and get shared instances
worker_resources = init_background_worker()
cm = worker_resources["cloud_manager"]  # FIX #3: Use shared instance

# --- Sidebar: Fund Management (V4.1 Hybrid) ---
st.sidebar.title("🏇 V4.1 Hybrid Strategy")

# User Request: Selectable Unit Price
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
ADMIN_PASS_CORRECT = cm.check_admin_pass(admin_pass_input)

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
        st.rerun()
    
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
    # Critical Alert System
    alert_active = False 
    if alert_active:
        st.error("🚨 CRITICAL: DATA MISMATCH - TRADING HALTED 🚨")
        st.stop()

    # Key Metrics
    st.markdown("### 📊 Live Performance (Endurance)")
    col1, col2, col3, col4 = st.columns(4)

    # Fetch Bets
    df_bets = pd.DataFrame()
    try:
        res_bets = supabase.table("bet_queue").select("*").execute()
        if res_bets.data:
            df_bets = pd.DataFrame(res_bets.data)
    except Exception as e:
        st.error(f"Error fetching bets: {e}")

    # Calculate Metrics
    today_invest = 0
    
    if not df_bets.empty and 'created_at' in df_bets.columns:
        df_bets['created_at'] = pd.to_datetime(df_bets['created_at'])
        df_today = df_bets[df_bets['created_at'].dt.date == datetime.date.today()]
        today_invest = df_today[df_today['status'] == 'purchased']['amount'].sum() if 'amount' in df_today.columns else 0
        
    col1.metric("Current Streak (Loses)", "0", delta_color="inverse")
    col2.metric("Today's Invest", f"¥{today_invest:,}")
    col3.metric("Daily Cap", f"¥{cm.get_daily_cap():,}")
    col4.metric("Engine Status", "STANDBY" if not is_active else "RUNNING", delta_color="normal" if is_active else "off")

    # Queue / EV Monitor
    st.subheader("🎯 Bet Queue & EV Analysis")
    if not df_bets.empty:
        df_bets = df_bets.sort_values('created_at', ascending=False)
        st.dataframe(
            df_bets[['created_at', 'race_id', 'horse_num', 'bet_type', 'status', 'details', 'amount']],
            use_container_width=True
        )
    else:
        st.info("No bets in queue yet.")

    # Odds Monitor
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
    
    # System Alerts
    st.subheader("🚨 System Logs & Alerts")
    try:
        res_logs = supabase.table("system_logs")\
            .select("*")\
            .order("timestamp", desc=True)\
            .limit(10)\
            .execute()
            
        if res_logs.data:
            df_logs = pd.DataFrame(res_logs.data)
            st.dataframe(
                df_logs[['timestamp', 'level', 'message', 'details']], 
                use_container_width=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Time", format="MM-DD HH:mm"),
                    "level": st.column_config.TextColumn("Level"), 
                    "message": st.column_config.TextColumn("Message"),
                    "details": st.column_config.TextColumn("Details"),
                }
            )
        else:
            st.caption("No system logs found.")
    except Exception as e:
        st.error(f"Failed to fetch logs: {e}")

    st.divider()
    st.markdown("### 📜 Trade History (Live Info)")
    
    # Switch from static CSV to Supabase 'bet_queue' (purchased items)
    try:
        # Fetch last 50 purchased bets
        res_history = supabase.table("bet_queue")\
            .select("*")\
            .eq("status", "purchased")\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
            
        if res_history.data:
            df_hist = pd.DataFrame(res_history.data)
            
            # Format Timestamp
            if 'created_at' in df_hist.columns:
                df_hist['created_at'] = pd.to_datetime(df_hist['created_at'])
            
            # Display Clean Table
            st.dataframe(
                df_hist[['created_at', 'race_id', 'horse_num', 'bet_type', 'amount', 'details']],
                use_container_width=True,
                column_config={
                    "created_at": st.column_config.DatetimeColumn("Time", format="MM-DD HH:mm"),
                    "amount": st.column_config.NumberColumn("Amount", format="¥%d"),
                    "horse_num": st.column_config.TextColumn("Horse"),
                    "details": st.column_config.TextColumn("Strategy Info"),
                }
            )
        else:
            st.info("ℹ️ No live trades recorded yet.")
            
    except Exception as e:
        st.error(f"Failed to fetch trade history: {e}")

with tab_compound:
    st.header("Compound Simulation")
    st.info("V4.1 Simulation Comparison available in previous version.")
