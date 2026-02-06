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

# --- Sidebar: Fund Management (V4.1 Hybrid) ---
st.sidebar.title("🏇 V4.1 Hybrid Strategy")
# st.sidebar.markdown("### 🛡️ Asset-Linked Slide")

# User Request: Selectable Unit Price (100, 1000, 10000)
unit_price = st.sidebar.selectbox("Base Unit Price (¥)", [100, 1000, 10000], index=0, help="初期投資ユニット額（スライド方式の基準）")
scale_factor = unit_price / 100  # Base simulation was 100 yen

st.sidebar.info(
    f"""
    **Current Strategy**
    - **Single**: EV > 2.0 (Spear)
    - **Wide**: EV > 1.34 (Shield)
    - **Unit**: ¥{unit_price:,} (+Slide)
    """
)

# --- Main Page ---
if not supabase:
    st.error("🚨 Supabase Connection Failed. Check Secrets.")
    st.stop()

# --- Tabs ---
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
    log_file = "trade_log_v4_1.csv"
    if os.path.exists(log_file):
        df_log = pd.read_csv(log_file)
        df_log['Date'] = pd.to_datetime(df_log['Date'])
        
        # --- Apply Scaling ---
        if scale_factor != 1.0:
            df_log['Bet'] = df_log['Bet'] * scale_factor
            df_log['Payout'] = df_log['Payout'] * scale_factor
            df_log['Balance'] = df_log['Balance'] * scale_factor
        df_log['Year'] = df_log['Date'].dt.year
        df_log['Month'] = df_log['Date'].dt.month
        
        # --- Filters ---
        st.markdown("##### 🕵️ Filter Criteria")
        f1, f2, f3, f4 = st.columns(4)
        
        df_view = df_log.copy()
        
        with f1:
            # Year Filter
            all_years = sorted(df_log['Year'].unique(), reverse=True)
            sel_years = st.multiselect("📅 Year", options=all_years, default=all_years[:1]) # Default to latest year
            if sel_years:
                df_view = df_view[df_view['Year'].isin(sel_years)]
        
        with f2:
            # Month Filter
            all_months = sorted(df_view['Month'].unique())
            sel_months = st.multiselect("🗓️ Month", options=all_months)
            if sel_months:
                df_view = df_view[df_view['Month'].isin(sel_months)]
                
        with f3:
            # Type Filter
            if not df_view.empty:
                unique_types = sorted(df_view['Type'].astype(str).unique())
                sel_types = st.multiselect("🏷️ Bet Type", options=unique_types)
                if sel_types:
                    df_view = df_view[df_view['Type'].isin(sel_types)]
                
        with f4:
            # Result Filter
            if not df_view.empty:
                unique_results = sorted(df_view['Result'].astype(str).unique())
                sel_results = st.multiselect("🏁 Result", options=unique_results)
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
            
            # Sort by Date desc for view
            df_display = df_view.sort_values('Date', ascending=False)
            
            # Clean Horse Number for Display (Handle 3.0 -> 3)
            def format_horse(val):
                try:
                    return str(int(float(val))) if '-' not in str(val) else val # Handle Single (3.0) and Wide (3-5)
                except:
                    return str(val)

            df_display['Horse'] = df_display['Horse'].apply(format_horse)
            
            st.dataframe(
                df_display.style.applymap(highlight_result, subset=['Result']),
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

with tab_compound:
    st.header("📈 Compound Simulation Comparison (V2 vs V3 vs V4 vs V4.1)")
    st.markdown("""
    **Strategy**: Asset-Linked Slide Method (Stepwise)
    - **Initial**: ¥100,000 | **Unit**: +¥100 per +¥100k
    - **Red (V2)**: Old Model (Failed) | **Blue (V3)**: V3 Adaptive 
    - **Green (V4)**: Hybrid (Single+Wide) | **Purple (V4.1)**: Relaxed Wide (Shield)
    """)
    
    csv_v2 = "compound_simulation_2023_2025.csv"
    csv_v3 = "compound_simulation_2023_2025_v3.csv"
    csv_v4 = "compound_simulation_2023_2025_v4.csv"
    csv_v4_1 = "compound_simulation_v4_1_wide_relaxed.csv"
    
    if os.path.exists(csv_v2) and os.path.exists(csv_v3):
        df_v2 = pd.read_csv(csv_v2)
        df_v3 = pd.read_csv(csv_v3)
        df_v4 = pd.read_csv(csv_v4) if os.path.exists(csv_v4) else df_v3.copy()
        df_v4_1 = pd.read_csv(csv_v4_1) if os.path.exists(csv_v4_1) else df_v3.copy()
        
        # Preprocess
        df_v2['date'] = pd.to_datetime(df_v2['date'])
        df_v3['date'] = pd.to_datetime(df_v3['date'])
        df_v4['date'] = pd.to_datetime(df_v4['date'])
        df_v4_1['date'] = pd.to_datetime(df_v4_1['date'])
        
        # Apply Scaling to Balance History
        if scale_factor != 1.0:
            df_v2['current_balance'] *= scale_factor
            df_v3['current_balance'] *= scale_factor
            df_v4['current_balance'] *= scale_factor
            df_v4_1['current_balance'] *= scale_factor
        
        # Metrics
        m_v3 = df_v3['current_balance'].iloc[-1]
        m_v4 = df_v4['current_balance'].iloc[-1]
        m_v4_1 = df_v4_1['current_balance'].iloc[-1]
        
        # Calculate Unit Acceleration (Target scales with unit)
        target_doubling = 200000 * scale_factor
        
        def get_days_to_reach(df, target):
            reached = df[df['current_balance'] >= target]
            return (reached.iloc[0]['date'] - df.iloc[0]['date']).days if not reached.empty else "N/A"
            
        acc_v3 = get_days_to_reach(df_v3, target_doubling)
        acc_v4_1 = get_days_to_reach(df_v4_1, target_doubling)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("V3 Balance", f"¥{m_v3:,.0f}")
        c2.metric("V4 Balance", f"¥{m_v4:,.0f}", delta=f"vs V3: ¥{m_v4-m_v3:,.0f}")
        c3.metric("V4.1 Balance", f"¥{m_v4_1:,.0f}", delta=f"vs V4: ¥{m_v4_1-m_v4:,.0f}")
        c4.metric(f"Days to ¥{target_doubling/1000:,.0f}k", f"{acc_v4_1} days", delta=f"{acc_v3 - acc_v4_1} days faster" if isinstance(acc_v3, int) and isinstance(acc_v4_1, int) else "---")

        # Chart
        st.subheader("Asset Curve Comparison")
        chart_data = pd.DataFrame({
            'Date': df_v3['date'],
            'V2 (Old)': df_v2.set_index('date')['current_balance'].reindex(df_v3['date'], method='ffill').values,
            'V3 (Single)': df_v3['current_balance'].values,
            'V4 (Hybrid)': df_v4.set_index('date')['current_balance'].reindex(df_v3['date'], method='ffill').values,
            'V4.1 (Relaxed)': df_v4_1.set_index('date')['current_balance'].reindex(df_v3['date'], method='ffill').values
        }).set_index('Date')
        
        st.line_chart(chart_data, color=["#FF4B4B", "#1f77b4", "#2ca02c", "#9467bd"]) # Red, Blue, Green, Purple
        
        # Data
        with st.expander("View V4.1 Log"):
            st.dataframe(df_v4_1)
            
    else:
        st.warning("Simulation files missing.")

# Footer
st.markdown("---")
st.caption("Hybrid EV 3.0 Engine | Powered by active-learning-agent")
