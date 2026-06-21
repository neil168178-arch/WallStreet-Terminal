import streamlit as st
import pandas as pd
from portfolio_engine import calculate_portfolio_pnl
from render_engine import render_dataframe

def render_portfolio_manager(is_etf_mode, fee_discount, save_callback):
    """獨立出來的投資存摺介面模組，徹底解決狀態鎖死問題"""
    
    # 🛡️ 1. 建立「強型別」的空白表格 (解決無法新增行的核心關鍵)
    # 之前無法新增，是因為 Streamlit 搞混了空表格裡的文字和數字格式
    empty_df = pd.DataFrame({
        "股票代號": pd.Series(dtype='str'),
        "持股數量(股)": pd.Series(dtype='int'),
        "總投資成本(元)": pd.Series(dtype='float')
    })

    # 🛡️ 2. 獲取當前模式的 DataFrame，如果為空就套用強型別空白表
    if is_etf_mode:
        if 'etf_portfolio' not in st.session_state or st.session_state.etf_portfolio.empty:
            st.session_state.etf_portfolio = empty_df.copy()
        current_df = st.session_state.etf_portfolio
        editor_key = "etf_editor_ui_key"
    else:
        if 'stock_portfolio' not in st.session_state or st.session_state.stock_portfolio.empty:
            st.session_state.stock_portfolio = empty_df.copy()
        current_df = st.session_state.stock_portfolio
        editor_key = "stock_editor_ui_key"

    # 🛡️ 3. 欄位格式嚴格綁定
    col_cfg = {
        "股票代號": st.column_config.TextColumn("代號 (必填)"),
        "持股數量(股)": st.column_config.NumberColumn("持股數量(股)", min_value=1, step=1),
        "總投資成本(元)": st.column_config.NumberColumn("總投資成本(元)", min_value=0.0, step=10.0)
    }

    # 4. 渲染編輯器
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config=col_cfg,
        key=editor_key
    )

    # 5. 回寫 Session State
    if is_etf_mode:
        st.session_state.etf_portfolio = edited_df
    else:
        st.session_state.stock_portfolio = edited_df

    # 6. 按鈕邏輯
    if st.button("☁️ 儲存投資組合至雲端資料庫", use_container_width=True):
        save_callback()

    if st.button("🔄 結算最新市值與真實損益", type="primary"):
        with st.spinner("連線交易所計算中..."):
            # 過濾掉空白列，避免計算引擎崩潰
            valid_df = edited_df.dropna(subset=["股票代號"])
            valid_df = valid_df[valid_df["股票代號"].astype(str).str.strip() != ""]
            
            if valid_df.empty:
                st.warning("⚠️ 您的存摺目前沒有任何有效的標的，請先在上方表格新增！")
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