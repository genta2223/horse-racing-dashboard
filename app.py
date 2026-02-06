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
tab_live, tab_monitor, tab_backtest, tab_compound = st.tabs(["📊 Live Dashboard", "🔍 Live Action Monitor", "📚 Backtest (2023-24)", "📈 Compound Sim (2023-25)"])

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

with tab_monitor:
    st.header("🔍 Live Action Monitor")
    st.markdown("Real-time trading log and historical Trade/Pass decisions.")
    
    # Load Logs
    log_file = "trade_log_v4.csv"
    if os.path.exists(log_file):
        df_log = pd.read_csv(log_file)
        df_log['Date'] = pd.to_datetime(df_log['Date'])
        
        # --- Filters ---
        f1, f2, f3 = st.columns(3)
        
        with f1:
            # Date Filter
            dates = sorted(df_log['Date'].dt.date.unique(), reverse=True)
            selected_date = st.selectbox("📅 Date", options=dates, index=0)
            
        # Base Data for Day
        df_view = df_log[df_log['Date'].dt.date == selected_date].copy()
        
        with f2:
            # Type Filter (Single/Wide)
            if not df_view.empty:
                unique_types = sorted(df_view['Type'].astype(str).unique())
                sel_types = st.multiselect("🏷️ Bet Type", options=unique_types, default=unique_types)
                if sel_types:
                    df_view = df_view[df_view['Type'].isin(sel_types)]
            else:
                st.write("No data")
                
        with f3:
            # Result Filter (WIN/LOSE)
            if not df_view.empty:
                unique_results = sorted(df_view['Result'].astype(str).unique())
                sel_results = st.multiselect("🏁 Result", options=unique_results, default=unique_results)
                if sel_results:
                    df_view = df_view[df_view['Result'].isin(sel_results)]

        # --- Summary Panel (Dynamic) ---
        if not df_view.empty:
            total_invest = df_view['Bet'].sum()
            total_payout = df_view['Payout'].sum()
            net_profit = total_payout - total_invest
            
            # Hit Rate calc - consider filtered view
            wins = len(df_view[df_view['Result'] == 'WIN'])
            total = len(df_view)
            hit_rate = (wins / total * 100) if total > 0 else 0
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Invest", f"¥{total_invest:,}")
            m2.metric("Payout", f"¥{total_payout:,}")
            m3.metric("Net Profit", f"¥{net_profit:,}", delta=f"{net_profit:,}")
            m4.metric("Hit Rate", f"{hit_rate:.1f}% ({wins}/{total})")
            
            st.divider()
            
            # Styled Table
            def highlight_result(val):
                color = 'green' if val == 'WIN' else 'red'
                return f'color: {color}; font-weight: bold'
            
            st.dataframe(
                df_view.style.applymap(highlight_result, subset=['Result']),
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    "Odds": st.column_config.NumberColumn("Odds", format="%.1f倍"),
                    "Prob": st.column_config.NumberColumn("AI Prob", format="%.1f%%"),
                    "EV": st.column_config.NumberColumn("EV", format="%.2f"),
                    "Bet": st.column_config.NumberColumn("Bet", format="¥%d"),
                    "Payout": st.column_config.NumberColumn("Payout", format="¥%d"),
                    "Result": st.column_config.TextColumn("Result"),
                    "Balance": st.column_config.LineChartColumn("Balance Trend")
                },
                use_container_width=True,
                height=500
            )
        else:
            st.info("No trades matched your filters.")
            
    else:
        st.warning(f"Trade Log ({log_file}) not found. Run V4 simulation first.")

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
    st.header("📈 Compound Simulation Comparison (V2 vs V3 vs V4)")
    st.markdown("""
    **Strategy**: Asset-Linked Slide Method (Stepwise)
    - **Initial**: ¥100,000 | **Unit**: +¥100 per +¥100k
    - **Red (V2)**: Old Model (Failed) | **Blue (V3)**: V3 Adaptive | **Green (V4)**: Hybrid (Single+Wide)
    """)
    
    csv_v2 = "compound_simulation_2023_2025.csv"
    csv_v3 = "compound_simulation_2023_2025_v3.csv"
    csv_v4 = "compound_simulation_2023_2025_v4.csv"
    
    if os.path.exists(csv_v2) and os.path.exists(csv_v3):
        df_v2 = pd.read_csv(csv_v2)
        df_v3 = pd.read_csv(csv_v3)
        df_v4 = pd.read_csv(csv_v4) if os.path.exists(csv_v4) else df_v3.copy() # Fallback
        
        # Preprocess
        df_v2['date'] = pd.to_datetime(df_v2['date'])
        df_v3['date'] = pd.to_datetime(df_v3['date'])
        df_v4['date'] = pd.to_datetime(df_v4['date'])
        
        # Metrics
        m_v2 = df_v2['current_balance'].iloc[-1]
        m_v3 = df_v3['current_balance'].iloc[-1]
        m_v4 = df_v4['current_balance'].iloc[-1]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Final Balance (V3)", f"¥{m_v3:,.0f}", delta=f"vs V2: ¥{m_v3-m_v2:,.0f}")
        c2.metric("Final Balance (V4)", f"¥{m_v4:,.0f}", delta=f"vs V3: ¥{m_v4-m_v3:,.0f}")
        c3.metric("Peak Balance (V4)", f"¥{df_v4['current_balance'].max():,.0f}")

        # Chart
        st.subheader("Asset Curve Comparison")
        chart_data = pd.DataFrame({
            'Date': df_v3['date'],
            'V2 (Old)': df_v2.set_index('date')['current_balance'].reindex(df_v3['date'], method='ffill').values,
            'V3 (Single)': df_v3['current_balance'].values,
            'V4 (Hybrid)': df_v4.set_index('date')['current_balance'].reindex(df_v3['date'], method='ffill').values
        }).set_index('Date')
        
        st.line_chart(chart_data, color=["#FF4B4B", "#1f77b4", "#2ca02c"]) # Red, Blue, Green
        
        # Data
        with st.expander("View Daily Log (V4 Hybrid)"):
            st.dataframe(df_v4)
            
    else:
        st.warning("Simulation files missing.")

# Footer
st.markdown("---")
st.caption("Hybrid EV 3.0 Engine | Powered by active-learning-agent")
