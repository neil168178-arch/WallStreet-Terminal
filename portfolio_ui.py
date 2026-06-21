import streamlit as st
import pandas as pd
from portfolio_engine import calculate_portfolio_pnl
from render_engine import render_dataframe

def render_portfolio_manager(is_etf_mode, fee_discount, save_callback):
    
    # 📖 白話文教學：如何使用記帳本
    with st.expander("📖 白話文教學：如何使用記帳本？", expanded=False):
        st.write("這是一個連線到雲端的記帳本。在表格裡輸入你手邊有買的標的代號、買了幾股（一張填 1000）、花了多少錢。輸入完記得按下「儲存至雲端」，接著按「結算損益」，系統就會幫你抓最新股價算出現賺多少！")

    current_df = st.session_state.etf_portfolio if is_etf_mode else st.session_state.stock_portfolio
    
    if current_df.empty:
        current_df = pd.DataFrame([{"股票代號": "", "持股數量(股)": 0, "總投資成本(元)": 0.0}])
    
    editor_key = "etf_editor_ui_key" if is_etf_mode else "stock_editor_ui_key"

    col_cfg = {
        "股票代號": st.column_config.TextColumn("標的代號 (例如: 2330.TW)"),
        "持股數量(股)": st.column_config.NumberColumn("持股數量(股)", min_value=0, step=1),
        "總投資成本(元)": st.column_config.NumberColumn("總投資成本(元)", min_value=0.0, step=10.0)
    }

    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config=col_cfg,
        key=editor_key
    )

    if is_etf_mode:
        st.session_state.etf_portfolio = edited_df
    else:
        st.session_state.stock_portfolio = edited_df

    if st.button("☁️ 儲存投資組合至雲端資料庫", use_container_width=True):
        save_callback()

    if st.button("🔄 結算最新市值與真實損益", type="primary"):
        with st.spinner("連線交易所計算中..."):
            valid_df = edited_df.dropna(subset=["股票代號"])
            valid_df = valid_df[valid_df["股票代號"].astype(str).str.strip() != ""]
            
            if valid_df.empty:
                st.warning("⚠️ 您的存摺目前沒有有效的標的，請先在表格輸入資料！")
                return
                
            pnl_df = calculate_portfolio_pnl(valid_df, fee_discount)
            
            if not pnl_df.empty:
                render_dataframe(pnl_df, hide_index=True)
                total_cost = pnl_df['總投資成本'].sum()
                total_value = pnl_df['目前總市值'].sum()
                total_profit = pnl_df['未實現損益'].sum()
                total_roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
                
                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("總投資成本", f"${total_cost:,}")
                c2.metric("目前總市值", f"${total_value:,}")
                c3.metric("帳面總損益", f"${total_profit:,}")
                c4.metric("整體報酬率", f"{total_roi:.1f}%")