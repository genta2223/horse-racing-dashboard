import streamlit as st
import pandas as pd
import datetime
import os
import json
from dotenv import load_dotenv
from supabase import create_client

# --- Config ---
st.set_page_config(page_title="Hybrid EV 2.0 Dashboard", layout="wide", page_icon="🏇")
load_dotenv()

# Supabase Connection Strategy
# 1. Try st.secrets (Streamlit Cloud)
# 2. Try os.getenv (Local .env via python-dotenv)

SUPABASE_URL = None
SUPABASE_KEY = None

# Helper to look for keys case-insensitively or in commonly used sections
def find_credentials():
    url, key = None, None
    
    # A. Check Streamlit Secrets
    try:
        # 1. Root level
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets:
            key = st.secrets["SUPABASE_KEY"]
            
        # 2. Nested [supabase] section (common pattern)
        if not url and "supabase" in st.secrets:
            section = st.secrets["supabase"]
            url = section.get("url") or section.get("URL") or section.get("SUPABASE_URL")
            key = section.get("key") or section.get("KEY") or section.get("SUPABASE_KEY")
            
    except FileNotFoundError:
        pass # No secrets.toml locally
    except Exception:
        pass # Other secrets errors

    # B. Check Environment Variables (Fallback)
    if not url:
        url = os.getenv("SUPABASE_URL")
    if not key:
        key = os.getenv("SUPABASE_KEY")
        
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

# --- Sidebar: Fund Management (V2 Endurance) ---
st.sidebar.title("🏇 Hybrid EV 2.0")
st.sidebar.markdown("### 🛡️ Endurance Mode")

unit_price = st.sidebar.number_input("Unit Price (Fixed)", value=1000, step=100, help="1点あたりの固定投資額")
ev_threshold = st.sidebar.number_input("EV Threshold", value=2.0, step=0.1, help="推奨閾値: 2.0")

st.sidebar.info(
    f"""
    **Current Strategy**
    - Fixed Bet: ¥{unit_price:,}
    - Min EV: {ev_threshold}
    - Logic: Endurance (No Cuts)
    """
)

# --- Main Page ---
if not supabase:
    st.error("🚨 Supabase Connection Failed. Check Secrets.")
    st.stop()

# --- Tabs ---
tab_live, tab_backtest, tab_compound = st.tabs(["📊 Live Dashboard", "📚 Backtest (2023-24)", "📈 Compound Sim (2023-25)"])

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
    streak = 0
    
    if not df_bets.empty and 'created_at' in df_bets.columns:
        df_bets['created_at'] = pd.to_datetime(df_bets['created_at'])
        df_today = df_bets[df_bets['created_at'].dt.date == datetime.date.today()]
        today_invest = len(df_today) * unit_price
        
    col1.metric("Current Streak (Loses)", "0", delta_color="inverse")
    col2.metric("Today's Invest", f"¥{today_invest:,}")
    col3.metric("Next Hit Recovery", "---")
    col4.metric("Status", "🟢 RUNNING")

    # 3. Queue / EV Monitor
    st.subheader("🎯 Bet Queue & EV Analysis")

    if not df_bets.empty:
        df_bets = df_bets.sort_values('created_at', ascending=False)
        st.dataframe(
            df_bets[['created_at', 'race_id', 'horse_num', 'bet_type', 'status', 'details']],
            use_container_width=True
        )
    else:
        st.info("No bets in queue yet.")

    # 4. Odds Monitor (0B32 Support)
    st.subheader("📈 Odds Monitor (Win vs Quinella)")

    try:
        # Note: Supabase defaults to 'created_at'. Adjust if your schema uses 'timestamp'.
        # Assuming 'created_at' based on standard schema.
        res_raw = supabase.table("raw_race_data").select("*").order("created_at", desc=True).limit(10).execute()
        if res_raw.data:
            raw_df = pd.DataFrame(res_raw.data)
            odds_rows = raw_df[raw_df['data_type'].isin(['0B31', '0B32'])]
            
            if not odds_rows.empty:
                # Use created_at for display
                st.dataframe(odds_rows[['created_at', 'data_type', 'count']])
                st.caption("Raw Data Log (Verify 0B32 arrival)")
            else:
                st.warning("No Odds Data (0B31/0B32) received recently.")
        else:
            st.warning("No Raw Data in DB.")
    except Exception as e:
        st.warning(f"⚠️ Could not fetch Raw Data monitor: {e}")

with tab_backtest:
    st.header("📚 Backtest Results (2023-2024)")
    st.markdown("Strategy: **Hybrid EV 2.0** (EV > 2.0, Fixed ¥1,000)")
    
    csv_path = "backtest_2023_2024_v2.csv"
    if os.path.exists(csv_path):
        df_bt = pd.read_csv(csv_path)
        
        # KPIs
        total_profit = df_bt['cumulative_profit'].iloc[-1]
        hit_rate = (df_bt['result'] == 1).mean() * 100
        total_bets = len(df_bt)
        max_dd = df_bt['drawdown'].min()
        roi = (df_bt['payout'].sum() / (total_bets * 1000)) * 100
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Net Profit", f"¥{total_profit:,.0f}")
        kpi2.metric("Hit Rate", f"{hit_rate:.2f}%")
        kpi3.metric("ROI", f"{roi:.1f}%")
        kpi4.metric("Max Drawdown", f"¥{max_dd:,.0f}")
        
        # Chart
        st.subheader("Equity Curve")
        st.line_chart(df_bt[['date', 'cumulative_profit']].set_index('date'))
        
        # Data
        st.subheader("Trade Log")
        st.dataframe(df_bt)
    else:
        st.warning(f"Backtest CSV not found: {csv_path}")

with tab_compound:
    st.header("📈 Compound Simulation (2023-2025)")
    st.markdown("""
    **Strategy**: Asset-Linked Slide Method
    - **Initial**: ¥100,000
    - **Unit**: +¥100 per +¥100k Asset
    - **Logic**: Hybrid EV 2.0 (EV > 2.0)
    """)
    
    comp_csv = "compound_simulation_2023_2025.csv"
    if os.path.exists(comp_csv):
        df_comp = pd.read_csv(comp_csv)
        
        # Metrics
        initial_bal = 100000
        final_bal = df_comp['current_balance'].iloc[-1]
        peak_bal = df_comp['current_balance'].max()
        max_unit = df_comp['unit_price'].max()
        roi_comp = ((final_bal - initial_bal) / initial_bal) * 100
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Final Balance", f"¥{final_bal:,.0f}", delta=f"{roi_comp:.1f}%")
        c2.metric("Peak Balance", f"¥{peak_bal:,.0f}")
        c3.metric("Max Unit Price", f"¥{max_unit:,}")
        c4.metric("Days Simulated", len(df_comp))
        
        # Chart
        st.subheader("Asset Curve (2023-2025)")
        st.line_chart(df_comp[['date', 'current_balance']].set_index('date'))
        
        # Data
        st.subheader("Daily Log")
        st.dataframe(df_comp)
    else:
        st.warning(f"Simulation CSV not found: {comp_csv}")

# Footer
st.markdown("---")
st.caption("Hybrid EV 2.0 Engine | Powered by active-learning-agent")
