import streamlit as st
import pandas as pd
import datetime
import os
import time
import threading
import sys
import json
import pytz
from dotenv import load_dotenv
from supabase import create_client

# Local Modules
try:
    from cloud_manager import CloudManager
    from worker_shopper import Shopper
    from worker_predictor_v4_1 import run_prediction_cycle
    from worker_result_scraper import scrape_race_results # Hybrid Scraper
except ImportError as e:
    st.error(f"Module Import Error: {e}")
    st.stop()

# ... (Config section unchanged) ...

# ... (Inside tab_results) ...

with tab_results:
    st.header("🏆 Race Results (Scraped / netkeiba)")
    
    col_res1, col_res2 = st.columns([1, 3])
    with col_res1:
        if st.button("🔄 Update Results Now"):
            with st.spinner("Scraping results..."):
                # Fetch today's race_ids from DB
                today_str = datetime.datetime.now(jst).strftime("%Y%m%d")
                res_rids = supabase.table("raw_race_data").select("race_id").eq("race_date", today_str).execute()
                if res_rids.data:
                    count = 0
                    progress_bar = st.progress(0)
                    total = len(res_rids.data)
                    
                    for i, r in enumerate(res_rids.data):
                        rid = r['race_id']
                        data = scrape_race_results(rid)
                        if data:
                            supabase.table("race_results").upsert(data).execute()
                            count += 1
                        progress_bar.progress((i + 1) / total)
                        time.sleep(0.5)
                    st.success(f"Updated {count} records!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("No races found for today to scrape.")

    # Show entries from race_results table
    try:
        res_r = supabase.table("race_results").select("*").order("timestamp", desc=True).limit(20).execute()


# --- Config ---
st.set_page_config(page_title="Hybrid EV 2.0 Commander", layout="wide", page_icon="🏇")
load_dotenv()

# --- Database Connection ---
def find_credentials() -> tuple[str | None, str | None]:
    """Find Supabase credentials from secrets or environment"""
    url, key = None, None
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if not url:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
    except:
        pass

    if not url: url = os.getenv("SUPABASE_URL")
    if not key: key = os.getenv("SUPABASE_KEY")
    return url, key

SUPABASE_URL, SUPABASE_KEY = find_credentials()

@st.cache_resource
def init_connection():
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

supabase = init_connection()
if not supabase:
    st.error("🚨 Supabase Connection Failed. Check Secrets.")
    st.stop()

# --- Background Worker (Maintains Shopper State) ---
@st.cache_resource
def init_background_worker():
    cm = CloudManager(supabase)
    shopper = Shopper(supabase)
    
    def background_loop():
        print("[BG] Worker Thread Started.")
        while True:
            try:
                # Hybrid Mode: Only run Shopper (Shopping logic handles approval check)
                # Prediction is manual or scheduled?
                # User config: Check if auto-bet is active (Global Switch)
                if cm.is_auto_bet_active():
                    # Run Prediction Cycle periodically? 
                    # For now just run shopper check
                    shopper.check_and_buy(daily_limit_override=cm.get_daily_cap())
                
                time.sleep(60) 
            except Exception as e:
                print(f"[BG] Loop Error: {e}")
                time.sleep(60)

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    return {"thread": t, "cloud_manager": cm, "shopper": shopper}

worker_resources = init_background_worker()
cm = worker_resources["cloud_manager"]

# --- Sidebar: Status & Config ---
st.sidebar.title("🏇 Commander's View")

# Time
jst = pytz.timezone('Asia/Tokyo')
now_jst = datetime.datetime.now(jst)
st.sidebar.caption(f"Time (JST): {now_jst.strftime('%Y-%m-%d %H:%M')}")

# Data Status Check
st.sidebar.markdown("### 📡 Data Status")

# Check JV Data (0B15) for today/tomorrow
today_str = now_jst.strftime("%Y%m%d")
tomorrow_str = (now_jst + datetime.timedelta(days=1)).strftime("%Y%m%d")

@st.cache_data(ttl=60)
def check_data_status(date_str):
    try:
        res = supabase.table("raw_race_data").select("count", count="exact").eq("data_type", "0B15").eq("race_date", date_str).execute()
        return res.count if res.count else 0
    except:
        return 0

count_today = check_data_status(today_str)
count_tomorrow = check_data_status(tomorrow_str)

st.sidebar.metric("Today's Data (0B15)", f"{count_today} records", delta="OK" if count_today > 0 else "MISSING", delta_color="normal" if count_today > 0 else "inverse")
st.sidebar.metric("Tomorrow's Data", f"{count_tomorrow} records", delta="OK" if count_tomorrow > 0 else "WAITING")

if count_today == 0 and count_tomorrow == 0:
    st.sidebar.error("⚠️ No race data found! Please upload via local script.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🏦 Controls")

# Admin
admin_pass = st.sidebar.text_input("Admin Password", type="password")
is_admin = cm.check_admin_pass(admin_pass)

is_active = cm.is_auto_bet_active()
status_label = "🟢 SYSTEM ONLINE" if is_active else "🔴 SYSTEM OFFLINE"
if is_admin:
    new_active = st.sidebar.toggle("Master Switch", value=is_active)
    if new_active != is_active:
        cm.set_auto_bet_active(new_active)
        st.rerun()
else:
    st.sidebar.info(status_label)

# --- Main Interface ---
tab_commander, tab_monitor, tab_results = st.tabs(["🎖️ Commander's Console", "🔍 Live Monitor", "🏆 Race Results"])

with tab_commander:
    st.header("🎯 Bet Approval Console")
    
    # Target Date
    target_date = st.date_input("Target Date", value=now_jst.date())
    target_date_str = target_date.strftime("%Y%m%d")
    
    # 1. Fetch Recommendations (Pending Bets)
    try:
        # Fetch bets for this date (simple filter by race_id prefix or date field if available)
        # raw_race_data doesn't have bet info. We query bet_queue.
        # bet_queue needs created_at filter? Or match race_id date.
        
        # Heuristic: fetch all pending/approved bets
        res = supabase.table("bet_queue").select("*").in_("status", ["pending", "approved"]).order("race_id").execute()
        
        all_bets = res.data if res.data else []
        
        # Filter by date in python (race_id usually starts with YYYYMMDD or close to it?)
        # Current race_id format: "0B15_20260208_..." or "20260208..."
        # Let's try to filter efficiently.
        
        display_bets = []
        for b in all_bets:
            # Check if race_id contains target date
            if target_date_str in b['race_id']:
                display_bets.append(b)
        
        if display_bets:
            st.info(f"✨ {len(display_bets)} Recommendations for {target_date_str}")
            
            # Prepare DataFrame for Editor
            df_bets = pd.DataFrame(display_bets)
            
            # Add 'Approve' column based on 'approved' status
            # If approved is None/False -> False
            df_bets['Approve'] = df_bets['approved'].fillna(False)
            
            # Columns to show
            cols = ['Approve', 'race_id', 'horse_num', 'bet_type', 'amount', 'details', 'status', 'id']
            
            edited_df = st.data_editor(
                df_bets[cols],
                column_config={
                    "Approve": st.column_config.CheckboxColumn(
                        "Approve?",
                        help="Check to approve this bet for purchase",
                        default=False,
                    ),
                    "amount": st.column_config.NumberColumn(
                        "Amount (¥)",
                        format="¥%d",
                    ),
                    "details": st.column_config.TextColumn(
                        "Strategy / Reason",
                        width="medium"
                    ),
                },
                disabled=["race_id", "horse_num", "bet_type", "status", "details", "id"],
                hide_index=True,
                key="bet_editor",
                num_rows="fixed"
            )
            
            # Save Changes Button
            if st.button("💾 Setup Approvals"):
                # Find changed rows
                count_updated = 0
                for index, row in edited_df.iterrows():
                    original = df_bets.iloc[index]
                    if row['Approve'] != original['Approve']:
                        # Update DB
                        # If Approve -> True, status remains pending (shopper picks it up)
                        # but we mark approved=True
                        try:
                            supabase.table("bet_queue").update({
                                "approved": bool(row['Approve']),
                                "approved_at": datetime.datetime.now().isoformat() if row['Approve'] else None
                            }).eq("id", row['id']).execute()
                            count_updated += 1
                        except Exception as e:
                            st.error(f"Update failed for {row['id']}: {e}")
                
                if count_updated > 0:
                    st.success(f"Updated {count_updated} bets!")
                    time.sleep(1)
                    st.rerun()
            
            # Bulk Actions (Admin Only)
            if is_admin:
                col_bulk1, col_bulk2 = st.columns(2)
                with col_bulk1:
                    if st.button("✅ Approve ALL Shown"):
                        for b in display_bets:
                            supabase.table("bet_queue").update({
                                "approved": True,
                                "approved_at": datetime.datetime.now().isoformat()
                            }).eq("id", b['id']).execute()
                        st.success("All Approved!")
                        st.rerun()
        else:
            st.info("No recommendations found for this date. Run Prediction or check data.")
            
    except Exception as e:
        st.error(f"Error fetching bets: {e}")

with tab_monitor:
    st.header("🔍 Live Action Monitor")
    
    # Refresh button
    if st.button("🔄 Refresh Logs"):
        st.rerun()

    # System Logs
    st.subheader("System Logs")
    res_logs = supabase.table("system_logs").select("*").order("timestamp", desc=True).limit(10).execute()
    if res_logs.data:
        df_logs = pd.DataFrame(res_logs.data)
        st.dataframe(df_logs[['timestamp', 'level', 'message', 'details']], use_container_width=True)

    st.divider()
    
    # Purchase History
    st.subheader("🛒 Purchase History")
    res_hist = supabase.table("bet_queue").select("*").eq("status", "purchased").order("created_at", desc=True).limit(20).execute()
    if res_hist.data:
        st.dataframe(pd.DataFrame(res_hist.data), use_container_width=True)

with tab_results:
    st.header("🏆 Race Results (Scraped / 0B12)")
    
    # Show entries from race_results table
    try:
        res_r = supabase.table("race_results").select("*").order("timestamp", desc=True).limit(20).execute()
        if res_r.data:
            df_res = pd.DataFrame(res_r.data)
            st.dataframe(df_res, use_container_width=True)
            
            # Hit Check Visualization (Simple)
            st.subheader("🎯 Hit Check")
            st.write("Comparing Purchase History with Results...")
            # (Advanced hit check logic would go here)
        else:
            st.info("No scraped results yet. Run 'worker_result_scraper.py'.")
            
        # Also show raw 0B12 data for cross-reference
        with st.expander("Raw 0B12 Data"):
            res_0b12 = supabase.table("raw_race_data").select("*").eq("data_type", "0B12").order("timestamp", desc=True).limit(20).execute()
            if res_0b12.data:
                st.dataframe(pd.DataFrame(res_0b12.data))
    except Exception as e:
        st.error(f"Error: {e}")
