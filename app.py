import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- ページ設定 ---
st.set_page_config(page_title="AI Horse Racing Dashboard", layout="wide")

st.title("🏇 AI Investment Dashboard")
st.markdown("### 資金管理戦略: Pattern C (Safety First)")

# --- サイドバー: 資金管理パラメータ ---
st.sidebar.header("⚙️ 資金管理設定")

initial_capital = st.sidebar.number_input("初期資金 (円)", value=10000, step=1000)
risk_pct = st.sidebar.slider("1日の投資上限 (% of 残高)", 1, 50, 10) # Pattern Cは10%推奨
cut_line_pct = st.sidebar.slider("損切り発動ライン (損失 %)", 10, 100, 50) # 50%以上の損失で翌日減額
recovery_factor = 0.5 # 損切り発動時の翌日投資縮小率

st.sidebar.markdown("---")
st.sidebar.info(f"現在の設定:\n\n資金の **{risk_pct}%** を上限に投資。\n当日の損失が投資額の **{cut_line_pct}%** を超えた場合、翌日は投資額を **半分** にします。")

# --- データ読み込み ---
# ※実運用ではGithubにCSVを上げるか、クラウドDBに繋ぎます
# ここではデモ用に、アップロード機能またはローカル配置を想定
uploaded_file = st.sidebar.file_uploader("予測CSVをアップロード", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    # 日付型変換
    # 柔軟に対応: 'Date', 'date', '日付' などを探す
    date_col = None
    for c in ['date', 'Date', '日付']:
        if c in df.columns:
            date_col = c
            break
    
    if date_col:
        df['date'] = pd.to_datetime(df[date_col])
    else:
        st.error("CSVに日付カラム ('date' または 'Date') が見つかりません。")
        st.stop()
    
    # --- シミュレーション実行関数 ---
    def run_simulation(data, init_cap, risk, cut_line):
        balance = init_cap
        history = []
        current_risk_modifier = 1.0 # 通常は1.0、損切り後は0.5など

        # 日付ごとに集計
        daily_groups = data.groupby('date')
        
        for date, group in daily_groups:
            # 1. その日の予算決定
            daily_budget = balance * (risk / 100) * current_risk_modifier
            
            # 予算が少なすぎる場合の最低保証（任意）
            if daily_budget < 1000 and balance > 1000:
                daily_budget = 1000
            elif balance <= 1000:
                daily_budget = balance # 全ツッパ（または終了）

            # 2. 購入対象の決定（AIスコア順などで予算内に収める処理が必要だが、簡略化のため全購入対象に均等配分とする等のロジック）
            # ここでは「予測フラグが立っている馬を、予算内で均等買い」と仮定
            # 実際にはオッズ判定などがここに入る
            
            # 簡易シミュレーション: データの 'profit' 列（100円買い時の損益）を使用
            # その日のトータル損益（100円単位）
            day_total_profit_unit = group['profit'].sum() # 100円で買った場合の損益合計
            day_invest_count = len(group) # 購入点数
            
            if day_invest_count == 0:
                history.append({'date': date, 'balance': balance, 'daily_profit': 0, 'drawdown': 0, 'status': '-'})
                continue

            # 1点あたりの購入額を決定（予算 ÷ 点数）
            unit_price = daily_budget // day_invest_count
            if unit_price < 100: unit_price = 100 # 最低単価
            
            actual_invest = unit_price * day_invest_count
            
            # 残高不足チェック
            if actual_invest > balance:
                actual_invest = balance
                if day_invest_count > 0:
                    unit_price = actual_invest // day_invest_count
            
            # その日の損益計算
            # (100円あたりの損益 / 100) * 実際の購入単価
            daily_profit = (day_total_profit_unit / 100) * unit_price
            
            # 残高更新
            balance += daily_profit
            
            # --- Pattern C: ドローダウン判定 ---
            # 損失額が投資額の cut_line % を超えたか？
            if daily_profit < 0 and abs(daily_profit) > (actual_invest * (cut_line / 100)):
                current_risk_modifier = recovery_factor # ブレーキ発動
                status = "🛑 CUT"
            else:
                current_risk_modifier = 1.0 # 正常運転
                status = "✅ OK"

            # 記録
            history.append({
                'date': date,
                'balance': int(balance),
                'daily_profit': int(daily_profit),
                'invest': int(actual_invest),
                'status': status
            })
            
            if balance <= 0:
                break
                
        return pd.DataFrame(history)

    # --- ボタンで実行 ---
    if st.button("🚀 シミュレーション開始"):
        # ※注意: CSVには 'profit' (100円購入時の損益) 列が必要と仮定しています
        if 'profit' not in df.columns:
            st.error("CSVに 'profit' 列（100円購入時の損益）が必要です。")
        else:
            sim_df = run_simulation(df, initial_capital, risk_pct, cut_line_pct)
            
            if sim_df.empty:
                st.warning("データ期間中に取引がありませんでした。")
            else:
                # --- 結果表示エリア ---
                col1, col2, col3 = st.columns(3)
                final_balance = sim_df.iloc[-1]['balance']
                profit_rate = ((final_balance - initial_capital) / initial_capital) * 100
                
                # 最大ドローダウン計算
                sim_df['peak'] = sim_df['balance'].cummax()
                sim_df['dd'] = (sim_df['balance'] - sim_df['peak']) / sim_df['peak'] * 100
                max_dd = sim_df['dd'].min()

                col1.metric("最終残高", f"{final_balance:,.0f} 円", f"{profit_rate:.1f}%")
                col2.metric("最大ドローダウン", f"{max_dd:.1f}%")
                col3.metric("現在モード", "安全運転中 (Pattern C)")

                # --- グラフ描画 ---
                st.subheader("📈 資産推移チャート")
                fig = px.line(sim_df, x='date', y='balance', title='資産推移', markers=True)
                # ドローダウン発生箇所を色付け等の高度な装飾も可能
                st.plotly_chart(fig, use_container_width=True)

                # --- 詳細データ ---
                st.subheader("📝 日次詳細ログ")
                st.dataframe(sim_df.sort_values('date', ascending=False).style.applymap(
                    lambda x: 'color: red' if isinstance(x, str) and 'CUT' in x else '', subset=['status']
                ))

else:
    st.info("👈 サイドバーから予測データCSV (profit列付き) をアップロードしてください")
    st.write("※ profit列 = (払戻金 - 100) です。")
    st.markdown("""
    ### CSVフォーマット例
    | date | target | profit |
    | :--- | :--- | :--- |
    | 2025-01-05 | 1 | 420 |
    | 2025-01-05 | 0 | -100 |
    """)
