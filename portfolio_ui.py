import streamlit as st
import pandas as pd
from portfolio_engine import calculate_portfolio_pnl
from render_engine import render_dataframe

def render_portfolio_manager(is_etf_mode, fee_discount, save_callback):
    
    # 📖 白話文教學：加入手機版專屬刪除教學
    with st.expander("📖 白話文教學：如何使用記帳本？", expanded=False):
        st.write("這是一個連線到雲端的記帳本。在表格裡輸入你手邊有買的標的代號、買了幾股（一張填 1000）、花了多少錢。輸入完記得按下「儲存至雲端」，接著按「結算損益」，系統就會幫你抓最新股價算出現賺多少！\n\n**📱 手機版刪除秘訣：**\n如果想要刪除已經賣掉的標的，只要在該列最前面的 **「🗑️刪除」** 欄位打勾 ✅，然後按下 **「☁️ 儲存至雲端資料庫」**，系統就會自動幫你清得乾乾淨淨！")

    current_df = st.session_state.etf_portfolio if is_etf_mode else st.session_state.stock_portfolio
    
    # 🌟 核心升級：確保 DataFrame 擁有專屬的刪除勾選欄位
    if current_df.empty:
        current_df = pd.DataFrame([{"🗑️刪除": False, "股票代號": "", "持股數量(股)": 0, "總投資成本(元)": 0.0}])
    elif "🗑️刪除" not in current_df.columns:
        # 將刪除欄位安插在最前面 (第 0 個位置)
        current_df.insert(0, "🗑️刪除", False)
    
    editor_key = "etf_editor_ui_key" if is_etf_mode else "stock_editor_ui_key"
    hint_ticker = "0050.TW" if is_etf_mode else "2330.TW"

    # 定義欄位 UI (加入打勾框)
    col_cfg = {
        "🗑️刪除": st.column_config.CheckboxColumn("刪除", default=False, width="small"),
        "股票代號": st.column_config.TextColumn(f"標的代號 (例如: {hint_ticker})"),
        "持股數量(股)": st.column_config.NumberColumn("持股數量(股)", min_value=0, step=1),
        "總投資成本(元)": st.column_config.NumberColumn("總投資成本(元)", min_value=0.0, step=10.0)
    }

    # 渲染資料編輯器
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config=col_cfg,
        key=editor_key
    )

    def process_deletion(df):
        """🧹 底層清洗器：過濾掉被打勾刪除的列"""
        cleaned = df[df["🗑️刪除"] != True].copy()
        # 強制將保留下來的列復原為 False，避免下次載入異常
        cleaned["🗑️刪除"] = False 
        return cleaned

    if st.button("☁️ 儲存投資組合至雲端資料庫", use_container_width=True):
        # 執行清洗動作
        cleaned_df = process_deletion(edited_df)
        if is_etf_mode:
            st.session_state.etf_portfolio = cleaned_df
        else:
            st.session_state.stock_portfolio = cleaned_df
        
        save_callback()
        st.rerun() # 🌟 強制重整畫面，讓刪除的列「視覺上」真正消失！

    if st.button("🔄 結算最新市值與真實損益", type="primary"):
        # 結算時也要執行清洗動作，避免算到已經打勾的廢棄股票
        cleaned_df = process_deletion(edited_df)
        if is_etf_mode:
            st.session_state.etf_portfolio = cleaned_df
        else:
            st.session_state.stock_portfolio = cleaned_df
            
        with st.spinner("連線交易所計算中..."):
            valid_df = cleaned_df.dropna(subset=["股票代號"])
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