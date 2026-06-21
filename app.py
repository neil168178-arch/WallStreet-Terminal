import streamlit as st
import pandas as pd
import plotly.graph_objects as go 
import os
from supabase import create_client, Client

# ==========================================
# 🧠 系統底層：標的智能分類器 (判斷是個股還是 ETF)
# ==========================================
def is_etf_ticker(ticker):
    """判斷代號是否為 ETF (例如 0050.TW 或 00679B.TW)"""
    if not ticker: return False
    tk = ticker.split('.')[0]
    # 如果代號開頭是 00，或包含英文字母 (不是純數字)，就判定為 ETF
    if tk.startswith('00') or not tk.isdigit():
        return True
    return False

def safe_is_etf(x):
    return is_etf_ticker(str(x)) if pd.notna(x) else False

# ==========================================
# ☁️ Supabase 雲端資料庫與身分驗證模組
# ==========================================
def get_supabase() -> Client:
    if 'supabase_client' not in st.session_state:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        st.session_state.supabase_client = create_client(url, key)
    return st.session_state.supabase_client

def load_user_data():
    sb = get_supabase()
    try:
        # 1. 讀取所有觀察名單，並【物理切割】成個股與 ETF 兩個宇宙
        res_watch = sb.table("watchlists").select("ticker").execute()
        all_tickers = [row['ticker'] for row in res_watch.data]
        st.session_state.stock_watchlist = [t for t in all_tickers if not is_etf_ticker(t)]
        st.session_state.etf_watchlist = [t for t in all_tickers if is_etf_ticker(t)]

        # 2. 讀取所有投資組合，並【物理切割】
        res_port = sb.table("portfolios").select("*").execute()
        if res_port.data:
            df = pd.DataFrame(res_port.data)
            df = df.rename(columns={"ticker": "股票代號", "shares": "持股數量(股)", "cost_basis": "總投資成本(元)"})
        else:
            df = pd.DataFrame(columns=["股票代號", "持股數量(股)", "總投資成本(元)"])
            
        st.session_state.stock_portfolio = df[~df['股票代號'].apply(safe_is_etf)].reset_index(drop=True)
        st.session_state.etf_portfolio = df[df['股票代號'].apply(safe_is_etf)].reset_index(drop=True)
    except Exception as e:
        st.error(f"⚠️ 無法讀取雲端資料：{e}")

def load_user_settings():
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        res = sb.table("user_settings").select("*").eq("user_id", user_id).execute()
        if res.data:
            settings = res.data[0]
            st.session_state.tg_token = settings.get("tg_token", "")
            st.session_state.tg_chat_id = settings.get("tg_chat_id", "")
            st.session_state.gemini_key = settings.get("gemini_key", "")
        else:
            st.session_state.tg_token, st.session_state.tg_chat_id, st.session_state.gemini_key = "", "", ""
    except Exception as e:
        st.error(f"⚠️ 讀取金鑰設定失敗：{e}")

def save_user_settings(tg_token, tg_chat_id, gemini_key):
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        data = {"user_id": user_id, "tg_token": tg_token, "tg_chat_id": tg_chat_id, "gemini_key": gemini_key}
        sb.table("user_settings").upsert(data).execute()
        st.session_state.tg_token = tg_token
        st.session_state.tg_chat_id = tg_chat_id
        st.session_state.gemini_key = gemini_key
        st.toast("🔐 金鑰已安全加密並儲存至雲端！", icon="✅")
    except Exception as e:
        st.error(f"⚠️ 儲存金鑰失敗：{e}")

def add_to_watchlist(ticker, is_etf):
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        sb.table("watchlists").insert({"user_id": user_id, "ticker": ticker}).execute()
        if is_etf: st.session_state.etf_watchlist.append(ticker)
        else: st.session_state.stock_watchlist.append(ticker)
        st.rerun()
    except Exception as e:
        st.error("⚠️ 該標的可能已在名單中，或資料庫連線異常。")

def remove_from_watchlist(ticker, is_etf):
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        sb.table("watchlists").delete().eq("user_id", user_id).eq("ticker", ticker).execute()
        if is_etf: st.session_state.etf_watchlist.remove(ticker)
        else: st.session_state.stock_watchlist.remove(ticker)
        st.rerun()
    except Exception as e:
        st.error(f"⚠️ 移除失敗：{e}")

def save_portfolio():
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    # 儲存時，將兩個宇宙的資料重新合併上傳到 Supabase
    df_combined = pd.concat([st.session_state.stock_portfolio, st.session_state.etf_portfolio], ignore_index=True)
    try:
        sb.table("portfolios").delete().eq("user_id", user_id).execute()
        records = []
        for _, row in df_combined.iterrows():
            if pd.notna(row["股票代號"]) and str(row["股票代號"]).strip() != "":
                records.append({
                    "user_id": user_id, "ticker": str(row["股票代號"]),
                    "shares": int(row["持股數量(股)"]) if pd.notna(row["持股數量(股)"]) else 0,
                    "cost_basis": float(row["總投資成本(元)"]) if pd.notna(row["總投資成本(元)"]) else 0
                })
        if records:
            sb.table("portfolios").insert(records).execute()
        st.toast("☁️ 投資組合已成功同步至 Supabase！", icon="✅")
    except Exception as e:
        st.error(f"☁️ 投資組合同步失敗：{e}")

# ==========================================
# 匯入所有核心運算引擎
# ==========================================
from data_engine import load_data
from strategy_engine import add_indicators
from visual_engine import setup_page, plot_advanced_chart
from crawler_engine import run_async_crawler, run_market_screener, resolve_ticker
from macro_engine import fetch_macro_data, plot_macro_dashboard
from ranking_engine import run_multi_factor_ranking 
from intraday_engine import fetch_intraday_data, plot_intraday_chart
from portfolio_engine import calculate_portfolio_pnl
from predict_engine import run_monte_carlo_simulation, plot_monte_carlo_forecast
from ai_engine import run_ai_prediction, plot_ml_prediction
from news_engine import fetch_stock_news, analyze_news_sentiment, plot_sentiment_gauge
from backtest_engine import (
    run_advanced_backtest, run_out_of_sample_optimization, 
    run_parameter_grid_search, plot_equity_curve, plot_optimization_heatmap, 
    run_portfolio_backtest
)
from render_engine import render_dataframe, translate_df, inject_custom_css
from notification_engine import send_telegram_notify, run_daily_signal_scanner 

# ==========================================
# 🔐 會員登入 / 註冊介面
# ==========================================
def auth_page():
    st.markdown("<h1 style='text-align: center; color: #19D3F3;'>🚀 華爾街量化終端機 SaaS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #E0E0E0;'>歡迎來到企業級量化交易平台，請登入以啟動您的專屬 AI 大腦。</p>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_signup = st.tabs(["🔑 系統登入", "📝 註冊新帳號"])
        sb = get_supabase()
        
        with tab_login:
            log_email = st.text_input("電子信箱", key="log_email")
            log_pwd = st.text_input("密碼", type="password", key="log_pwd")
            if st.button("登入系統", use_container_width=True, type="primary"):
                with st.spinner("驗證身分中..."):
                    try:
                        res = sb.auth.sign_in_with_password({"email": log_email, "password": log_pwd})
                        st.session_state.logged_in = True
                        st.session_state.user_email = res.user.email
                        st.success("登入成功！正在載入您的專屬資料庫...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 登入失敗：請檢查帳號密碼是否正確。")
                        
        with tab_signup:
            st.info("💡 註冊完全免費！我們不會洩漏您的任何資訊。")
            reg_email = st.text_input("輸入電子信箱", key="reg_email")
            reg_pwd = st.text_input("設定密碼 (至少 6 碼)", type="password", key="reg_pwd")
            if st.button("註冊帳號", use_container_width=True):
                with st.spinner("建立雲端資料庫中..."):
                    try:
                        res = sb.auth.sign_up({"email": reg_email, "password": reg_pwd})
                        st.success("🎉 註冊成功！請切換到「登入」分頁進行登入。")
                    except Exception as e:
                        st.error(f"❌ 註冊失敗：{e}")

# ==========================================
# 🏠 主程式 UI 
# ==========================================
def main_app():
    inject_custom_css()
    
    if 'stock_watchlist' not in st.session_state: load_user_data()
    if 'tg_token' not in st.session_state: load_user_settings()
        
    st.sidebar.markdown(f"### 👤 {st.session_state.user_email}")
    if st.sidebar.button("🚪 安全登出", use_container_width=True):
        get_supabase().auth.sign_out()
        st.session_state.clear()
        st.rerun()

    if st.button("🔄 刷新全站數據", use_container_width=True):
        st.cache_data.clear() 
        st.rerun()
    st.caption("💡 點擊可清除快取，獲取市場最新鮮的數據！")

    st.sidebar.markdown("---")
    
    # ==========================================
    # 🌟 核心雙擎切換器
    # ==========================================
    st.sidebar.markdown("### ⚙️ 終端機雙核心系統")
    app_mode = st.sidebar.radio(
        "切換您的獨立操作系統：", 
        ["📈 個股波段系統", "📊 ETF 存股系統"]
    )
    is_etf_mode = (app_mode == "📊 ETF 存股系統")

    # 根據模式決定要操作哪一個資料庫
    active_watchlist = st.session_state.etf_watchlist if is_etf_mode else st.session_state.stock_watchlist

    if is_etf_mode:
        st.sidebar.info("🌐 目前位於：ETF 資產配置宇宙")
        placeholder_add = "例如：0050, 國泰永續高股息, 元大美債"
        default_search = "0050"
        sys_name = "ETF"
    else:
        st.sidebar.success("🔥 目前位於：個股基本面宇宙")
        placeholder_add = "例如：台積電, 2330, 鴻海"
        default_search = "台積電"
        sys_name = "個股"

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 系統導航")
    page = st.sidebar.radio("選擇操作工具", [
        f"🏠 {sys_name} 主控儀表板 (總覽)", 
        f"📋 {sys_name} 名單總覽 (報價牆)", 
        f"🎯 {sys_name} 深度分析 (單檔)", 
        f"🌍 {sys_name} 組合回測 (多檔)"
    ])
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### 📝 {sys_name} 雲端名單管理")
    new_stock_input = st.sidebar.text_input(f"➕ 新增{sys_name}", placeholder=placeholder_add)
    
    if st.sidebar.button("加入觀察名單", use_container_width=True):
        if new_stock_input:
            new_stock = resolve_ticker(new_stock_input)
            if new_stock is None: 
                st.sidebar.error(f"⚠️ 找不到「{new_stock_input}」！")
            else:
                is_etf = is_etf_ticker(new_stock)
                # 🛑 終極防呆機制：嚴格阻止跨宇宙加入標的
                if not is_etf_mode and is_etf:
                    st.sidebar.error(f"⚠️ 攔截！「{new_stock}」是 ETF，請切換至【ETF 存股系統】再加入！")
                elif is_etf_mode and not is_etf:
                    st.sidebar.error(f"⚠️ 攔截！「{new_stock}」是個股，請切換至【個股波段系統】再加入！")
                elif new_stock not in active_watchlist: 
                    add_to_watchlist(new_stock, is_etf)
                else: 
                    st.sidebar.warning(f"⚠️ 該{sys_name}已在名單中！")

    if active_watchlist:
        remove_stock = st.sidebar.selectbox(f"🗑️ 刪除{sys_name}", [""] + active_watchlist)
        if st.sidebar.button("移除", use_container_width=True):
            if remove_stock in active_watchlist: 
                remove_from_watchlist(remove_stock, is_etf_mode)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ✈️ 盤後推播與 AI 鑰匙")
    tg_token_input = st.sidebar.text_input("🤖 TG Bot Token", value=st.session_state.get('tg_token', ''), type="password")
    tg_chat_id_input = st.sidebar.text_input("💬 TG Chat ID", value=st.session_state.get('tg_chat_id', ''), type="password")
    gemini_key_input = st.sidebar.text_input("🧠 Gemini AI 鑰匙", value=st.session_state.get('gemini_key', ''), type="password")

    if st.sidebar.button("💾 記憶我的專屬金鑰 (安全儲存)", use_container_width=True):
        save_user_settings(tg_token_input, tg_chat_id_input, gemini_key_input)
        
    st.sidebar.markdown("---")
    strategy_dict_sidebar = {
        'ma_cross': '1️⃣ 均線交叉 (適合抓長趨勢)', 'macd_cross': '2️⃣ MACD 突破 (適合抓爆發力)',
        'rsi_reversion': '3️⃣ RSI 抄底 (適合跌深反彈)', 'bb_breakout': '4️⃣ 布林通道 (適合抓突破箱型)', 'combined': '5️⃣ 👑 多因子濾網 (勝率最高)'
    }
    inv_strat_side = {v: k for k, v in strategy_dict_sidebar.items()}
    scan_strategy_name = st.sidebar.selectbox("🎯 監控策略", list(inv_strat_side.keys()))
    
    if st.sidebar.button(f"🚀 執行 {sys_name} 雷達掃描", type="primary", use_container_width=True):
        if tg_token_input and tg_chat_id_input:
            with st.spinner("啟動雷達，掃描訊號中..."):
                success, msg = run_daily_signal_scanner(active_watchlist, inv_strat_side[scan_strategy_name], tg_token_input, tg_chat_id_input)
                if success: st.sidebar.success(msg)
                else: st.sidebar.error(msg)
        else:
            st.sidebar.warning("⚠️ 掃描前請務必輸入 Telegram Token 與 Chat ID！")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💸 真實交易成本設定")
    fee_discount = st.sidebar.slider("券商手續費折扣", 0.1, 1.0, 0.6, 0.05)
    slippage_input = st.sidebar.slider("💧 滑價懲罰 (%)", 0.0, 1.0, 0.2, 0.1) 
    slippage_pct = slippage_input / 100.0

    # ==========================================
    # 分頁核心邏輯
    # ==========================================
    if "主控儀表板" in page:
        st.markdown(f"## 🏠 {sys_name} 專屬主控儀表板")
        
        tab0, tab1, tab2 = st.tabs(["🌐 總經大局觀", f"💼 我的 {sys_name} 存摺", "🏆 AI 量化選股評分"])

        with tab0:
            macro_df = fetch_macro_data()
            if not macro_df.empty: 
                st.plotly_chart(plot_macro_dashboard(macro_df), use_container_width=True)

        with tab1:
            # 🛡️ 升級一：定義明確的表格欄位格式，防止新增時型態錯亂
            col_cfg = {
                "股票代號": st.column_config.TextColumn("代號 (必填)"),
                "持股數量(股)": st.column_config.NumberColumn("持股數量(股)", min_value=1, step=1),
                "總投資成本(元)": st.column_config.NumberColumn("總投資成本(元)", min_value=0.0, step=100.0)
            }

            # 🛡️ 升級二：根據模式隔離，並給予專屬的 Key (身分證)
            if is_etf_mode:
                st.session_state.etf_portfolio = st.data_editor(
                    st.session_state.etf_portfolio, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    column_config=col_cfg,
                    key="etf_editor_key"  # 👈 ETF 專屬身分證
                )
                pnl_df = calculate_portfolio_pnl(st.session_state.etf_portfolio, fee_discount)
            else:
                st.session_state.stock_portfolio = st.data_editor(
                    st.session_state.stock_portfolio, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    column_config=col_cfg,
                    key="stock_editor_key" # 👈 個股專屬身分證
                )
                pnl_df = calculate_portfolio_pnl(st.session_state.stock_portfolio, fee_discount)

            if st.button("☁️ 儲存投資組合至雲端資料庫", use_container_width=True): 
                save_portfolio()

            if st.button("🔄 結算最新市值與真實損益", type="primary"):
                with st.spinner("連線交易所計算中..."):
                    if not pnl_df.empty:
                        render_dataframe(pnl_df, hide_index=True)
                        total_cost, total_value, total_profit = pnl_df['總投資成本'].sum(), pnl_df['目前總市值'].sum(), pnl_df['未實現損益'].sum()
                        total_roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
                        st.markdown("---")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("總投資成本", f"${total_cost:,}")
                        c2.metric("目前總市值", f"${total_value:,}")
                        c3.metric("帳面總損益", f"${total_profit:,}")
                        c4.metric("整體報酬率", f"{total_roi:.1f}%")

        with tab2:
            st.markdown("### 🏆 觀察名單多因子量化評分")
            if is_etf_mode:
                # 🛑 專業隔離：ETF 不看財報本益比，所以在此模式下封鎖此功能
                st.warning("⚠️ **系統提示：** ETF 屬於「基金」性質，並無傳統財報之本益比與 EPS，因此不適用於『多因子基本面評分模型』。此功能僅開放於【個股波段系統】。")
            else:
                if st.button("⚡ 啟動量化評分引擎", type="primary"): 
                    with st.spinner("核心引擎正在幫全市場打分數..."):
                        ranking_result = run_multi_factor_ranking(active_watchlist)
                        render_dataframe(ranking_result, hide_index=False)

    elif "名單總覽" in page:
        st.markdown(f"## 📋 {sys_name} 即時報價牆")
        
        if not active_watchlist: st.warning(f"⚠️ 你的 {sys_name} 名單是空的，請先在左邊欄位新增！")
        else:
            if st.button("🔄 獲取最新報價", type="primary"): st.cache_data.clear()
            cols = st.columns(4)
            with st.spinner("連線交易所抓取中..."):
                for i, ticker in enumerate(active_watchlist):
                    df = load_data(ticker, period="5d")
                    if df is not None and len(df) >= 2:
                        l_price, p_price = df['Close'].iloc[-1], df['Close'].iloc[-2]
                        cols[i % 4].metric(f"🏷️ {ticker}", f"{l_price:.2f}", f"{l_price - p_price:.2f} ({(l_price - p_price)/p_price*100:.2f}%)")
                    else: cols[i % 4].metric(f"🏷️ {ticker}", "無資料", "-")
            st.markdown("---")
            with st.spinner("啟動爬蟲抓取中..."):
                crawler_res = run_async_crawler(active_watchlist)
                render_dataframe(crawler_res, hide_index=True)

    elif "深度分析" in page:
        st.markdown(f"## 🎯 {sys_name} 深度 X光機")
        
        target_stock = resolve_ticker(st.text_input(f"🔍 搜尋想分析的 {sys_name}", value=default_search))
        
        if not target_stock: st.warning(f"⚠️ 找不到該 {sys_name}。")
        else:
            # 🛑 防止在單檔分析頁面輸入錯誤宇宙的股票
            if is_etf_mode and not is_etf_ticker(target_stock):
                st.error("⚠️ 系統攔截：您搜尋的是『個股』，請先至側邊欄切換至【個股波段系統】才能查看！")
            elif not is_etf_mode and is_etf_ticker(target_stock):
                st.error("⚠️ 系統攔截：您搜尋的是『ETF』，請先至側邊欄切換至【ETF 存股系統】才能查看！")
            else:
                tabA, tabB, tabC, tabD, tabF, tabG, tabH = st.tabs([
                    "⚡ 盤中心電圖", "📈 技術看盤畫布", "⏳ 時光機回測", "🔮 未來預測", 
                    "📰 AI 讀新聞", "🤖 AI 猜漲跌", "💰 該買幾張？"
                ])
                
                with tabA:
                    df, name = fetch_intraday_data(target_stock)
                    if not df.empty: st.plotly_chart(plot_intraday_chart(df, target_stock, name), use_container_width=True)
                
                with tabB:
                    df_tech = load_data(target_stock, period="1y") 
                    if not df_tech.empty: 
                        st.plotly_chart(plot_advanced_chart(add_indicators(df_tech), target_stock), use_container_width=True)
                
                with tabC:
                    st.markdown(f"### 🤖 時光機回測大腦 ({target_stock})")
                    strategy_dict = {
                        'ma_cross': '1️⃣ 均線交叉 (長線順勢)', 'macd_cross': '2️⃣ MACD 突破 (抓短線爆發)',
                        'rsi_reversion': '3️⃣ RSI 抄底 (人棄我取)', 'bb_breakout': '4️⃣ 布林通道 (箱型突破)', 'combined': '5️⃣ 👑 終極多因子濾網'
                    }
                    inv_strategy_dict = {v: k for k, v in strategy_dict.items()}
                    selected_strategy_name = st.selectbox("🧠 選擇你想測試的招式", list(inv_strategy_dict.keys()))
                    selected_strategy = inv_strategy_dict[selected_strategy_name]

                    c1, c2, c3, c4 = st.columns(4)
                    with c1: initial_cap = st.number_input("💵 你準備帶多少錢回過去？", min_value=10000, value=100000, step=10000)
                    with c2: stop_loss = st.number_input("🛑 虧多少要跑(%)", min_value=1.0, value=5.0, step=1.0)
                    with c3: take_profit = st.number_input("🎉 賺多少入袋(%)", min_value=1.0, value=15.0, step=1.0)
                    with c4: 
                        short_ma = st.number_input("短均線天數", min_value=3, value=5, step=1)
                        long_ma = st.number_input("長均線天數", min_value=10, value=20, step=1)

                    st.markdown("#### 🛡️ 保護機制 (打勾啟動)")
                    f1, f2 = st.columns(2)
                    with f1: use_filter = st.checkbox("大跌時不准買 (60MA 長線趨勢保護)", value=True)
                    with f2: allow_short = st.checkbox("允許放空 (股價跌也能賺)", value=False)

                    st.markdown("#### 📈 進階：ATR 動態停損利")
                    use_atr = st.checkbox("啟動 ATR 智能出場", value=False)
                    if use_atr:
                        a1, a2, a3 = st.columns(3)
                        with a1: risk_pct_input = st.number_input("單筆最多賠掉本金的 %", min_value=0.5, value=2.0, step=0.5)
                        with a2: atr_sl_mult = st.number_input("停損放多寬 (x ATR)", min_value=1.0, value=2.0, step=0.5)
                        with a3: atr_tp_mult = st.number_input("停利抓多遠 (x ATR)", min_value=1.0, value=4.0, step=0.5)
                    else:
                        risk_pct_input, atr_sl_mult, atr_tp_mult = 2.0, 2.0, 4.0

                    st.markdown("---")
                    def prepare_backtest_data():
                        return load_data(target_stock, period="2y")

                    col_btn1, col_btn2 = st.columns(2)
                    if col_btn1.button("🚀 測試這套策略！", type="primary", use_container_width=True):
                        with st.spinner("時光機運算中..."):
                            df_backtest = prepare_backtest_data()
                            if not df_backtest.empty:
                                equity_df, trades_df, metrics = run_advanced_backtest(
                                    df=df_backtest, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf_mode, 
                                    strategy_type=selected_strategy, use_trend_filter=use_filter, 
                                    stop_loss_pct=stop_loss/100, take_profit_pct=take_profit/100,
                                    short_window=int(short_ma), long_window=int(long_ma), 
                                    use_atr=use_atr, atr_sl_mult=atr_sl_mult, atr_tp_mult=atr_tp_mult, risk_pct=risk_pct_input, 
                                    allow_short=allow_short, use_chips_filter=False, slippage_pct=slippage_pct
                                )
                                if metrics:
                                    st.markdown("#### 📊 最終成績單")
                                    m1, m2, m3, m4 = st.columns(4)
                                    m1.metric("最終總資金", f"${int(metrics['Final Equity']):,}")
                                    m2.metric("總共賺了", f"{metrics['ROI (%)']:.1f}%")
                                    m3.metric("勝率", f"{metrics['Win Rate (%)']:.1f}%")
                                    m4.metric("最大跌幅", f"{metrics['Max Drawdown (%)']:.1f}%")
                                    st.plotly_chart(plot_equity_curve(equity_df, title=f"📈 {selected_strategy_name} 資金成長曲線"), use_container_width=True)

                    if col_btn2.button("🛡️ 防作弊盲測 (OOS)", use_container_width=True):
                        with st.spinner("切分未知時空..."):
                            df_opt = prepare_backtest_data()
                            if not df_opt.empty:
                                best_p, best_roi, oos_eq, oos_tr, oos_m = run_out_of_sample_optimization(
                                    df=df_opt, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf_mode, 
                                    strategy_type=selected_strategy, use_filter=use_filter, 
                                    sl=stop_loss/100, tp=take_profit/100,
                                    use_atr=use_atr, a_sl=atr_sl_mult, a_tp=atr_tp_mult, r_pct=risk_pct_input, 
                                    allow_short=allow_short, use_chips=False, slippage_pct=slippage_pct
                                )
                                st.success(f"🏆 系統自己找出的最佳參數：短 {best_p[0]} 天 / 長 {best_p[1]} 天 (訓練期獲利: {best_roi:.1f}%)")
                                if oos_m: st.plotly_chart(plot_equity_curve(oos_eq, title='📉 盲測期真實資金曲線'), use_container_width=True)

                    st.markdown("---")
                    st.markdown("### 🧪 熱力圖找參數")
                    if st.button("🔥 一鍵暴力破解最佳參數", type="secondary", use_container_width=True):
                        with st.spinner("正在瘋狂測試海量參數組合..."):
                            df_opt = load_data(target_stock, period="2y")
                            if not df_opt.empty:
                                heatmap_data, best_row = run_parameter_grid_search(
                                    df=df_opt, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf_mode, 
                                    strategy_type=selected_strategy, use_filter=use_filter, 
                                    sl=stop_loss/100, tp=take_profit/100,
                                    use_atr=use_atr, atr_sl_mult=atr_sl_mult, atr_tp_mult=atr_tp_mult, risk_pct=risk_pct_input, 
                                    allow_short=allow_short, slippage_pct=slippage_pct
                                )
                                if heatmap_data is not None:
                                    st.success(f"🏆 破解完成！最強參數組合為：**短 {int(best_row['Short_MA'])}MA / 長 {int(best_row['Long_MA'])}MA**，可創造 **{best_row['ROI']:.2f}%** 報酬率！")
                                    st.plotly_chart(plot_optimization_heatmap(heatmap_data), use_container_width=True)

                with tabD:
                    if st.button("🔮 啟動平行宇宙模擬器", type="primary"):
                        df_pred = load_data(target_stock, period="1y")
                        if not df_pred.empty:
                            sim_df, percent_df, f_dates = run_monte_carlo_simulation(df_pred)
                            if sim_df is not None: st.plotly_chart(plot_monte_carlo_forecast(df_pred, sim_df, percent_df, f_dates, target_stock), use_container_width=True)
                
                with tabF:
                    st.markdown(f"### 📰 新聞與情緒解析 ({target_stock})")
                    if not gemini_key_input:
                        st.warning("⚠️ 必須先在側欄輸入 Gemini 鑰匙。")
                    else:
                        if st.button("🧠 請 AI 幫我讀完最新新聞", type="primary", use_container_width=True):
                            with st.spinner("🤖 閱讀中..."):
                                news_df = fetch_stock_news(target_stock)
                                if not news_df.empty:
                                    ai_result = analyze_news_sentiment(news_df, gemini_key_input)
                                    if "error" in ai_result:
                                        st.error(ai_result["error"])
                                    else:
                                        st.plotly_chart(plot_sentiment_gauge(ai_result.get("score", 50), ai_result.get("sentiment", "中立")), use_container_width=True)
                                        st.success(f"💡 **AI 懶人包：**\n{ai_result.get('summary', '無摘要')}")
                                else:
                                    st.warning("⚠️ 找不到近期新聞。")
                
                with tabG:
                    if st.button("🧠 叫 AI 預測明天漲跌", type="primary"):
                        df_ai = load_data(target_stock, period="1y")
                        if not df_ai.empty:
                            prob_up, importance = run_ai_prediction(df_ai)
                            if prob_up is not None: st.plotly_chart(plot_ml_prediction(prob_up, importance), use_container_width=True)
                
                with tabH:
                    st.markdown(f"### 💰 資金控管建議")
                    df_pos = load_data(target_stock, period="3mo")
                    if df_pos is not None and not df_pos.empty and len(df_pos) > 15:
                        prev_close = df_pos['Close'].shift(1)
                        tr = pd.concat([df_pos['High'] - df_pos['Low'], (df_pos['High'] - prev_close).abs(), (df_pos['Low'] - prev_close).abs()], axis=1).max(axis=1)
                        atr_14 = tr.rolling(window=14).mean().iloc[-1]
                        latest_close = df_pos['Close'].iloc[-1]

                        c1, c2, c3 = st.columns(3)
                        with c1: user_capital = st.number_input("💵 預計投資金額", min_value=10000, value=500000, step=50000)
                        with c2: risk_tolerance = st.slider("⚠️ 最大虧損 %", 0.5, 5.0, 2.0, 0.5)
                        with c3: atr_multiplier = st.slider("📏 停損寬度 (x ATR)", 1.0, 5.0, 2.0, 0.5)

                        st.markdown("---")
                        max_loss_amount = user_capital * (risk_tolerance / 100.0)
                        stop_loss_dist = atr_14 * atr_multiplier
                        stop_loss_price = latest_close - stop_loss_dist

                        if stop_loss_dist > 0:
                            recommended_shares = int(max_loss_amount / stop_loss_dist)
                            actual_invest_amount = recommended_shares * latest_close
                            if actual_invest_amount > user_capital:
                                recommended_shares = int(user_capital / latest_close)
                                actual_invest_amount = recommended_shares * latest_close

                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("目前價格", f"${latest_close:.2f}")
                            m2.metric("逃命價位", f"${stop_loss_price:.2f}")
                            m3.metric("建議買進股數", f"{recommended_shares:,} 股")
                            m4.metric("需花費資金", f"${actual_invest_amount:,.0f}")
                            st.success(f"> **💡 戰略分析：** 如果買進 **{recommended_shares:,} 股**，就算崩盤觸發逃命價，你也只會損失大約 **${int(max_loss_amount):,}**，完美控制在 **{risk_tolerance}%** 的風險內！")

    elif "組合回測" in page:
        st.markdown(f"## 🌍 {sys_name} 組合大回測")
            
        if not active_watchlist:
            st.warning(f"⚠️ 你的 {sys_name} 名單是空的，請先新增！")
            return

        strategy_dict_port = {
            'ma_cross': '1️⃣ 均線交叉 (長線)', 'macd_cross': '2️⃣ MACD (爆發)',
            'rsi_reversion': '3️⃣ RSI (抄底)', 'bb_breakout': '4️⃣ 布林通道 (突破)', 'combined': '5️⃣ 👑 終極多因子'
        }
        inv_strategy_dict_port = {v: k for k, v in strategy_dict_port.items()}
        selected_strategy_name_port = st.selectbox("🧠 核心策略", list(inv_strategy_dict_port.keys()))
        selected_strategy_port = inv_strategy_dict_port[selected_strategy_name_port]

        c1, c2, c3 = st.columns(3)
        with c1: port_cap = st.number_input("💰 總資金規模", min_value=100000, value=1000000, step=100000)
        with c2: short_ma_p = st.number_input("短均線", min_value=3, value=5, step=1, key='p_s')
        with c3: long_ma_p = st.number_input("長均線", min_value=10, value=20, step=1, key='p_l')

        f1, f2, f3 = st.columns(3)
        with f1: use_filter_p = st.checkbox("🛡️ 啟動 60MA 保護傘", value=True, key='p_f')
        with f2: allow_short_p = st.checkbox("🐻 允許放空", value=False, key='p_sh')
        with f3: max_alloc = st.slider("單檔最高資金佔比", 0.1, 1.0, 0.2, 0.1)
        
        use_atr_p = st.checkbox("🛡️ 啟用 ATR 動態防護網", value=True, key='p_atr')
        if use_atr_p:
            a1, a2, a3 = st.columns(3)
            with a1: risk_pct_p = st.number_input("單筆風險 (%)", value=2.0, step=0.5, key='p_r')
            with a2: atr_sl_p = st.number_input("停損 (x ATR)", value=2.0, step=0.5, key='p_sl')
            with a3: atr_tp_p = st.number_input("停利 (x ATR)", value=4.0, step=0.5, key='p_tp')
        else:
            risk_pct_p, atr_sl_p, atr_tp_p = 2.0, 2.0, 4.0
            
        st.markdown("---")
        if st.button(f"🌍 啟動 {sys_name} 歷史回測", type="primary", use_container_width=True):
            with st.spinner(f"正在掃描所有名單，執行交叉運算..."):
                data_dict = {}
                for tk in active_watchlist:
                    df = load_data(tk, period="2y")
                    if not df.empty: data_dict[tk] = df
                
                if data_dict:
                    eq_df, tr_df, metrics = run_portfolio_backtest(
                        data_dict=data_dict, initial_capital=port_cap, fee_discount=fee_discount, 
                        strategy_type=selected_strategy_port, use_filter=use_filter_p, 
                        sl_pct=0.05, tp_pct=0.10, short_window=int(short_ma_p), long_window=int(long_ma_p), 
                        use_atr=use_atr_p, atr_sl_mult=atr_sl_p, atr_tp_mult=atr_tp_p, risk_pct=risk_pct_p, 
                        allow_short=allow_short_p, slippage_pct=slippage_pct, max_alloc_per_ticker=max_alloc
                    )
                    if metrics:
                        st.markdown("#### 📊 回測戰報")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("兩年後總資金變為", f"${int(metrics['Final Equity']):,}")
                        m2.metric("兩年總獲利率", f"{metrics['ROI (%)']:.1f}%")
                        m3.metric("勝率", f"{metrics['Win Rate (%)']:.1f}%", f"交易了 {metrics['Total Trades']} 次")
                        m4.metric("最大跌幅", f"{metrics['Max Drawdown (%)']:.1f}%")
                        st.plotly_chart(plot_equity_curve(eq_df, title='🌍 資金累積曲線'), use_container_width=True)

if __name__ == "__main__":
    setup_page() 
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: auth_page()
    else: main_app()