import streamlit as st
import pandas as pd
import plotly.graph_objects as go 
import os
from supabase import create_client, Client

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
        # 讀取觀察名單與投資組合
        res_watch = sb.table("watchlists").select("ticker").execute()
        st.session_state.watchlist = [row['ticker'] for row in res_watch.data]

        res_port = sb.table("portfolios").select("*").execute()
        if res_port.data:
            df = pd.DataFrame(res_port.data)
            df = df.rename(columns={"ticker": "股票代號", "shares": "持股數量(股)", "cost_basis": "總投資成本(元)"})
            st.session_state.portfolio = df[["股票代號", "持股數量(股)", "總投資成本(元)"]]
        else:
            st.session_state.portfolio = pd.DataFrame({"股票代號": [], "持股數量(股)": [], "總投資成本(元)": []})
    except Exception as e:
        st.error(f"⚠️ 無法讀取雲端資料：{e}")

def load_user_settings():
    """從雲端保險箱讀取使用者的專屬 API 金鑰"""
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
            st.session_state.tg_token = ""
            st.session_state.tg_chat_id = ""
            st.session_state.gemini_key = ""
    except Exception as e:
        st.error(f"⚠️ 讀取金鑰設定失敗：{e}")

def save_user_settings(tg_token, tg_chat_id, gemini_key):
    """將金鑰安全地存入雲端保險箱"""
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        data = {
            "user_id": user_id,
            "tg_token": tg_token,
            "tg_chat_id": tg_chat_id,
            "gemini_key": gemini_key
        }
        # 使用 upsert (若無則新增，若有則更新)
        sb.table("user_settings").upsert(data).execute()
        st.session_state.tg_token = tg_token
        st.session_state.tg_chat_id = tg_chat_id
        st.session_state.gemini_key = gemini_key
        st.toast("🔐 金鑰已安全加密並儲存至您的專屬雲端保險箱！", icon="✅")
    except Exception as e:
        st.error(f"⚠️ 儲存金鑰失敗：{e}")

def add_to_watchlist(ticker):
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        sb.table("watchlists").insert({"user_id": user_id, "ticker": ticker}).execute()
        st.session_state.watchlist.append(ticker)
        st.rerun()
    except Exception as e:
        st.error("⚠️ 該標的可能已在名單中，或資料庫連線異常。")

def remove_from_watchlist(ticker):
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    try:
        sb.table("watchlists").delete().eq("user_id", user_id).eq("ticker", ticker).execute()
        st.session_state.watchlist.remove(ticker)
        st.rerun()
    except Exception as e:
        st.error(f"⚠️ 移除失敗：{e}")

def save_portfolio():
    sb = get_supabase()
    user_id = sb.auth.get_user().user.id
    df = st.session_state.portfolio
    try:
        sb.table("portfolios").delete().eq("user_id", user_id).execute()
        records = []
        for _, row in df.iterrows():
            if pd.notna(row["股票代號"]) and str(row["股票代號"]).strip() != "":
                records.append({
                    "user_id": user_id,
                    "ticker": str(row["股票代號"]),
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
    
    # 🌟 啟動時自動從保險箱讀取資料
    if 'watchlist' not in st.session_state:
        load_user_data()
    if 'tg_token' not in st.session_state:
        load_user_settings()
        
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
    st.sidebar.markdown("### 🧭 系統導航")
    
    page = st.sidebar.radio("選擇操作模式", [
        "🏠 主控儀表板 (總覽)", 
        "📋 觀察名單總覽 (報價牆)", 
        "🎯 個股深度分析 (單檔)", 
        "🌍 投資組合回測 (多檔)"
    ], help="這裡是你切換各種超強工具的地方！")
    
    # ==========================================
    # 🌟 核心升級：ETF 與個股模式切換器
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 終端機操作模式")
    app_mode = st.sidebar.radio(
        "選擇您的分析標的：", 
        ["📈 個股波段模式", "📊 ETF 存股模式"]
    )

    if app_mode == "📈 個股波段模式":
        st.sidebar.success("目前模式：個股基本面與技術分析")
        placeholder_add = "例如：台積電, 2330"
        default_search = "台積電"
    else:
        st.sidebar.info("目前模式：ETF 基金與資產配置")
        placeholder_add = "例如：0050, 元大美債"
        default_search = "0050"

    # ==========================================

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📝 雲端名單管理")
    new_stock_input = st.sidebar.text_input("➕ 新增標的", placeholder=placeholder_add, help="把你想關注的標的加入『觀察名單』，系統會幫你 24 小時盯著它！")
    if st.sidebar.button("加入觀察名單", use_container_width=True):
        if new_stock_input:
            new_stock = resolve_ticker(new_stock_input)
            if new_stock is None: st.sidebar.error(f"⚠️ 找不到「{new_stock_input}」！")
            elif new_stock not in st.session_state.watchlist: add_to_watchlist(new_stock)
            else: st.sidebar.warning("⚠️ 該標的已在您的觀察名單中了！")

    if st.session_state.watchlist:
        remove_stock = st.sidebar.selectbox("🗑️ 刪除標的", [""] + st.session_state.watchlist, help="想取消關注誰？從這裡刪除。")
        if st.sidebar.button("移除", use_container_width=True):
            if remove_stock in st.session_state.watchlist: remove_from_watchlist(remove_stock)

    st.sidebar.markdown("---")
    # 🌟 金鑰輸入區塊
    st.sidebar.markdown("### ✈️ 盤後推播與 AI 鑰匙")
    tg_token_input = st.sidebar.text_input("🤖 TG Bot Token", value=st.session_state.get('tg_token', ''), type="password", help="在 Telegram 搜尋 @BotFather 創建機器人取得的 Token")
    tg_chat_id_input = st.sidebar.text_input("💬 TG Chat ID", value=st.session_state.get('tg_chat_id', ''), type="password", help="在 Telegram 搜尋 @userinfobot 獲取你的數字 ID")
    gemini_key_input = st.sidebar.text_input("🧠 Gemini AI 鑰匙", value=st.session_state.get('gemini_key', ''), type="password", help="填入 Google AI 金鑰，解鎖系統閱讀新聞的能力！")

    if st.sidebar.button("💾 記憶我的專屬金鑰 (安全儲存)", use_container_width=True):
        save_user_settings(tg_token_input, tg_chat_id_input, gemini_key_input)
        
    st.sidebar.markdown("---")
    if st.sidebar.button("🔔 測試 TG 推播連線"):
        if tg_token_input and tg_chat_id_input:
            msg = send_telegram_notify(tg_token_input, tg_chat_id_input, "🤖 <b>華爾街量化終端機</b>\n系統連線成功，Telegram 專屬推播功能正常運作中！🚀")
            if msg.startswith("✅"): st.sidebar.success(msg)
            else: st.sidebar.error(msg)
        else:
            st.sidebar.warning("請先輸入上方兩組 Telegram 設定！")

    strategy_dict_sidebar = {
        'ma_cross': '1️⃣ 均線交叉 (適合抓長趨勢)', 'macd_cross': '2️⃣ MACD 突破 (適合抓爆發力)',
        'rsi_reversion': '3️⃣ RSI 抄底 (適合跌深反彈)', 'bb_breakout': '4️⃣ 布林通道 (適合抓突破箱型)', 'combined': '5️⃣ 👑 多因子濾網 (勝率最高)'
    }
    inv_strat_side = {v: k for k, v in strategy_dict_sidebar.items()}
    scan_strategy_name = st.sidebar.selectbox("🎯 監控策略", list(inv_strat_side.keys()), help="你希望系統用哪一招幫你挑標的？")
    
    if st.sidebar.button("🚀 執行盤後雷達掃描", type="primary", use_container_width=True):
        if tg_token_input and tg_chat_id_input:
            with st.spinner("啟動雷達，掃描全市場訊號中..."):
                success, msg = run_daily_signal_scanner(st.session_state.watchlist, inv_strat_side[scan_strategy_name], tg_token_input, tg_chat_id_input)
                if success: st.sidebar.success(msg)
                else: st.sidebar.error(msg)
        else:
            st.sidebar.warning("⚠️ 掃描前請務必輸入 Telegram Token 與 Chat ID！")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💸 真實交易成本設定")
    fee_discount = st.sidebar.slider("券商手續費折扣", 0.1, 1.0, 0.6, 0.05, help="你開戶的券商給你打幾折？(例如 6折請選 0.6)")
    slippage_input = st.sidebar.slider("💧 滑價懲罰 (%)", 0.0, 1.0, 0.2, 0.1, help="實戰中不一定能買到最漂亮的價格。設定滑價，讓回測結果更接近真實世界！") 
    slippage_pct = slippage_input / 100.0

    # ==========================================
    # 分頁核心邏輯
    # ==========================================
    if page == "🏠 主控儀表板 (總覽)":
        st.markdown("## 🏠 主控儀表板")
        st.info("👋 **歡迎來到指揮中心！** 這裡可以看一眼世界經濟大局、管理你的投資存摺，還能讓系統幫你的觀察名單打分數！")
        
        tab0, tab1, tab2 = st.tabs(["🌐 總經大局觀", "💼 我的投資存摺", "🏆 AI 量化選股評分"])

        with tab0:
            with st.expander("📖 白話文教學：為什麼要看總經？", expanded=False):
                st.write("股市就像海浪，總體經濟（總經）就是月球引力。通膨太高、央行升息，大盤資金就會被抽走；反之就會有大牛市！看懂大環境，才不會逆勢而為。")
            macro_df = fetch_macro_data()
            if not macro_df.empty: 
                st.plotly_chart(plot_macro_dashboard(macro_df), use_container_width=True)

        with tab1:
            with st.expander("📖 白話文教學：如何使用記帳本？", expanded=False):
                st.write("這是一個連線到雲端的記帳本。在表格裡輸入你手邊有買的標的代號、買了幾股（一張填 1000）、花了多少錢。輸入完記得按下「儲存至雲端」，接著按「結算損益」，系統就會幫你抓最新股價算出現賺多少！")
            
            st.session_state.portfolio = st.data_editor(st.session_state.portfolio, num_rows="dynamic", use_container_width=True)
            if st.button("☁️ 儲存投資組合至雲端資料庫", use_container_width=True): save_portfolio()

            if st.button("🔄 結算最新市值與真實損益", type="primary"):
                with st.spinner("連線交易所計算中..."):
                    pnl_df = calculate_portfolio_pnl(st.session_state.portfolio, fee_discount)
                    if not pnl_df.empty:
                        render_dataframe(pnl_df, hide_index=True)
                        total_cost, total_value, total_profit = pnl_df['總投資成本'].sum(), pnl_df['目前總市值'].sum(), pnl_df['未實現損益'].sum()
                        total_roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
                        st.markdown("---")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("你的總投資成本", f"${total_cost:,}")
                        c2.metric("換算目前總市值", f"${total_value:,}")
                        c3.metric("目前帳面總損益", f"${total_profit:,}")
                        c4.metric("整體報酬率", f"{total_roi:.1f}%")

        with tab2:
            st.markdown("### 🏆 觀察名單多因子量化評分")
            with st.expander("📖 白話文教學：這分數怎麼算的？", expanded=True):
                st.write("不知道手邊的名單該先買哪檔嗎？系統會用華爾街最紅的「多因子模型」幫標的打分 (滿分100)：\n\n1. **便宜度 (本益比)**：越便宜分數越高。\n2. **獲利力 (EPS)**：公司越會賺錢分數越高。\n3. **強勢度 (乖離率)**：最近趨勢越猛分數越高。\n\n⚠️ **【重要提示】** 這個分數是「排名機制(PR值)」，意思是標的互相比較出來的名次。如果你左邊的觀察名單**只有1檔標的**，那它當然是全班第一名，會得到三個100分！建議多加幾檔，分數才會精準喔！")
            
            if st.button("⚡ 啟動量化評分引擎", type="primary"): 
                with st.spinner("10 核心引擎正在幫全市場打分數..."):
                    ranking_result = run_multi_factor_ranking(st.session_state.watchlist)
                    render_dataframe(ranking_result, hide_index=False)

    elif page == "📋 觀察名單總覽 (報價牆)":
        st.markdown("## 📋 即時報價與基本面牆")
        st.info("👋 這裡列出了你所有關注標的的即時價格，以及它們的「健康檢查表（基本面）」。")
        
        if not st.session_state.watchlist: st.warning("⚠️ 你的觀察名單是空的，請先在左邊欄位新增！")
        else:
            if st.button("🔄 獲取最新報價與健康檢查表", type="primary"): st.cache_data.clear()
            cols = st.columns(4)
            with st.spinner("連線交易所抓取中..."):
                for i, ticker in enumerate(st.session_state.watchlist):
                    df = load_data(ticker, period="5d")
                    if df is not None and len(df) >= 2:
                        l_price, p_price = df['Close'].iloc[-1], df['Close'].iloc[-2]
                        cols[i % 4].metric(f"🏷️ {ticker}", f"{l_price:.2f}", f"{l_price - p_price:.2f} ({(l_price - p_price)/p_price*100:.2f}%)")
                    else: cols[i % 4].metric(f"🏷️ {ticker}", "無資料", "-")
            st.markdown("---")
            with st.spinner("啟動非同步爬蟲抓取財報中..."):
                crawler_res = run_async_crawler(st.session_state.watchlist)
                render_dataframe(crawler_res, hide_index=True)

    elif page == "🎯 個股深度分析 (單檔)":
        mode_text = app_mode.split(' ')[1] # 擷取字眼: "個股波段模式" 或 "ETF"
        st.markdown(f"## 🎯 深度 X光機 ({mode_text})")
        
        # 🌟 這裡套用了上面的動態預設搜尋
        target_stock = resolve_ticker(st.text_input(f"🔍 搜尋想分析的標的", value=default_search, help="輸入代號或中文名稱，按下 Enter！"))
        
        if not target_stock: st.warning("⚠️ 找不到該標的。")
        else:
            tabA, tabB, tabC, tabD, tabF, tabG, tabH = st.tabs([
                "⚡ 盤中心電圖", "📈 技術看盤畫布", "⏳ 時光機回測", "🔮 未來預測", 
                "📰 AI 讀新聞", "🤖 AI 猜漲跌", "💰 該買幾張？"
            ])
            
            with tabA:
                with st.expander("📖 這是什麼圖？"): st.write("這是『分時閃電圖』，展示這檔標的在『今天盤中』每一分鐘的走勢，適合愛玩當沖的短線玩家看主力動向。")
                df, name = fetch_intraday_data(target_stock)
                if not df.empty: st.plotly_chart(plot_intraday_chart(df, target_stock, name), use_container_width=True)
            
            with tabB:
                with st.expander("📖 指標小教室 (看不懂圖看這裡)"): 
                    st.write("**1. K線 (紅綠蠟燭)**：紅色代表今天漲，綠色代表今天跌。\n**2. 均線 (MA)**：大家的平均成本。股價在線上面代表大家都在賺錢，趨勢偏多。\n**3. RSI**：判斷是不是『漲過頭』或『跌過頭』的溫度計。低於 30 常常會觸底反彈。\n**4. MACD**：看『動能』。快線穿過慢線往上，就是常聽到的『黃金交叉』買點！")
                df_tech = load_data(target_stock, period="1y") 
                if not df_tech.empty: 
                    st.plotly_chart(plot_advanced_chart(add_indicators(df_tech), target_stock), use_container_width=True)
            
            with tabC:
                st.markdown(f"### 🤖 時光機回測大腦 ({target_stock})")
                with st.expander("📖 什麼是回測？怎麼玩？", expanded=True):
                    st.write("「回測」就是坐時光機回到兩年前，如果我們完全遵守某一種『買賣紀律』，現在會賺多少錢？\n這能幫你打破迷思，找出真正能賺錢的方法！")

                strategy_dict = {
                    'ma_cross': '1️⃣ 均線交叉 (長線順勢)', 'macd_cross': '2️⃣ MACD 突破 (抓短線爆發)',
                    'rsi_reversion': '3️⃣ RSI 抄底 (人棄我取)', 'bb_breakout': '4️⃣ 布林通道 (箱型突破)', 'combined': '5️⃣ 👑 終極多因子濾網'
                }
                inv_strategy_dict = {v: k for k, v in strategy_dict.items()}
                selected_strategy_name = st.selectbox("🧠 選擇你想測試的招式", list(inv_strategy_dict.keys()))
                selected_strategy = inv_strategy_dict[selected_strategy_name]

                c1, c2, c3, c4 = st.columns(4)
                with c1: initial_cap = st.number_input("💵 你準備帶多少錢回過去？", min_value=10000, value=100000, step=10000)
                with c2: stop_loss = st.number_input("🛑 虧多少要跑(%)", min_value=1.0, value=5.0, step=1.0, help="跌破這%數，系統自動認賠出場")
                with c3: take_profit = st.number_input("🎉 賺多少入袋(%)", min_value=1.0, value=15.0, step=1.0, help="賺到這%數，系統自動獲利了結")
                with c4: 
                    short_ma = st.number_input("短均線天數", min_value=3, value=5, step=1)
                    long_ma = st.number_input("長均線天數", min_value=10, value=20, step=1)

                st.markdown("#### 🛡️ 保護機制 (打勾啟動)")
                f1, f2 = st.columns(2)
                with f1: use_filter = st.checkbox("大跌時不准買 (60MA 長線趨勢保護)", value=True)
                with f2: allow_short = st.checkbox("允許放空 (股價跌也能賺)", value=False)

                st.markdown("#### 📈 進階：ATR 動態停損利 (高手必備)")
                use_atr = st.checkbox("啟動 ATR 智能出場 (不再用死板的 % 數停損)", value=False)
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
                            is_etf = target_stock.startswith('00')
                            equity_df, trades_df, metrics = run_advanced_backtest(
                                df=df_backtest, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf, 
                                strategy_type=selected_strategy, use_trend_filter=use_filter, 
                                stop_loss_pct=stop_loss/100, take_profit_pct=take_profit/100,
                                short_window=int(short_ma), long_window=int(long_ma), 
                                use_atr=use_atr, atr_sl_mult=atr_sl_mult, atr_tp_mult=atr_tp_mult, risk_pct=risk_pct_input, 
                                allow_short=allow_short, use_chips_filter=False, slippage_pct=slippage_pct
                            )
                            if metrics:
                                st.markdown("#### 📊 最終成績單")
                                m1, m2, m3, m4 = st.columns(4)
                                m1.metric("最終總資金", f"${int(metrics['Final Equity']):,}", help="扣掉手續費後，你口袋最後剩的錢")
                                m2.metric("總共賺了", f"{metrics['ROI (%)']:.1f}%")
                                m3.metric("勝率", f"{metrics['Win Rate (%)']:.1f}%", help="買 10 次有幾次是賺錢的？")
                                m4.metric("最痛的一波", f"{metrics['Max Drawdown (%)']:.1f}%", help="這兩年來，你的資金曾經從高點跌掉多少？(這個數字越小越好)")
                                st.plotly_chart(plot_equity_curve(equity_df, title=f"📈 {selected_strategy_name} 資金成長曲線"), use_container_width=True)
                                if not trades_df.empty: 
                                    st.write("📜 **這兩年的每一筆交易明細：**")
                                    render_dataframe(trades_df, hide_index=True)

                if col_btn2.button("🛡️ 防作弊盲測 (OOS)", use_container_width=True):
                    with st.spinner("切分未知時空..."):
                        df_opt = prepare_backtest_data()
                        if not df_opt.empty:
                            is_etf = target_stock.startswith('00')
                            best_p, best_roi, oos_eq, oos_tr, oos_m = run_out_of_sample_optimization(
                                df=df_opt, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf, 
                                strategy_type=selected_strategy, use_filter=use_filter, 
                                sl=stop_loss/100, tp=take_profit/100,
                                use_atr=use_atr, a_sl=atr_sl_mult, a_tp=atr_tp_mult, r_pct=risk_pct_input, 
                                allow_short=allow_short, use_chips=False, slippage_pct=slippage_pct
                            )
                            st.success(f"🏆 系統自己找出的最佳參數：短 {best_p[0]} 天 / 長 {best_p[1]} 天 (訓練期獲利: {best_roi:.1f}%)")
                            if oos_m: st.plotly_chart(plot_equity_curve(oos_eq, title='📉 盲測期真實資金曲線 (沒有作弊的未來績效)'), use_container_width=True)

                st.markdown("---")
                st.markdown("### 🧪 電腦幫我找神級參數！(熱力圖)")
                with st.expander("📖 白話文教學：熱力圖怎麼看？"):
                    st.write("不知道均線要設幾天？按下去，系統會直接測試 100 種組合！圖表上**紅色代表賠錢，綠色代表賺錢**。找出一大片都是綠色的區域，那就是最抗跌、最穩定的神級參數！")
                
                if st.button("🔥 一鍵暴力破解最佳參數", type="secondary", use_container_width=True):
                    with st.spinner("正在瘋狂測試海量參數組合..."):
                        df_opt = load_data(target_stock, period="2y")
                        if not df_opt.empty:
                            is_etf = target_stock.startswith('00')
                            heatmap_data, best_row = run_parameter_grid_search(
                                df=df_opt, initial_capital=initial_cap, fee_discount=fee_discount, is_etf=is_etf, 
                                strategy_type=selected_strategy, use_filter=use_filter, 
                                sl=stop_loss/100, tp=take_profit/100,
                                use_atr=use_atr, atr_sl_mult=atr_sl_mult, atr_tp_mult=atr_tp_mult, risk_pct=risk_pct_input, 
                                allow_short=allow_short, slippage_pct=slippage_pct
                            )
                            if heatmap_data is not None:
                                st.success(f"🏆 破解完成！最強參數組合為：**短 {int(best_row['Short_MA'])}MA / 長 {int(best_row['Long_MA'])}MA**，可創造 **{best_row['ROI']:.2f}%** 報酬率！")
                                st.plotly_chart(plot_optimization_heatmap(heatmap_data), use_container_width=True)

            with tabD:
                with st.expander("📖 什麼是蒙地卡羅預測？"):
                    st.write("就像奇異博士看未來一樣！電腦會用高等數學，模擬這檔標的未來 1000 種可能的走勢，然後告訴你：它一個月後上漲的機率到底大不大？")
                if st.button("🔮 啟動平行宇宙模擬器", type="primary"):
                    df_pred = load_data(target_stock, period="1y")
                    if not df_pred.empty:
                        sim_df, percent_df, f_dates = run_monte_carlo_simulation(df_pred)
                        if sim_df is not None: st.plotly_chart(plot_monte_carlo_forecast(df_pred, sim_df, percent_df, f_dates, target_stock), use_container_width=True)
            
            with tabF:
                st.markdown(f"### 📰 最新新聞與 AI 投資情緒解析 ({target_stock})")
                with st.expander("📖 為什麼要讓 AI 讀新聞？"):
                    st.write("新聞太多看不完？讓 Google 的 AI 機器人 1 秒內讀完 15 篇最新新聞，並直接幫你畫成情緒儀表板。指針偏向紅色代表市場正在恐慌，偏向藍綠色代表貪婪噴出！")
                
                if not gemini_key_input:
                    st.warning("⚠️ 必須先在左側欄輸入 Gemini 鑰匙才能解鎖此功能。")
                else:
                    if st.button("🧠 請 AI 幫我讀完最新新聞", type="primary", use_container_width=True):
                        with st.spinner("🤖 機器人正在上網閱讀新聞..."):
                            news_df = fetch_stock_news(target_stock)
                            if not news_df.empty:
                                ai_result = analyze_news_sentiment(news_df, gemini_key_input)
                                if "error" in ai_result:
                                    st.error(ai_result["error"])
                                else:
                                    st.plotly_chart(plot_sentiment_gauge(ai_result.get("score", 50), ai_result.get("sentiment", "中立")), use_container_width=True)
                                    st.success(f"💡 **AI 給你的懶人包：**\n{ai_result.get('summary', '無摘要')}")
                                    with st.expander("📄 點我查看 AI 剛剛讀了哪些新聞？"):
                                        render_dataframe(news_df, hide_index=True, link_col="新聞連結")
                            else:
                                st.warning("⚠️ 找不到近期新聞。")
            
            with tabG:
                with st.expander("📖 什麼是機器學習？"):
                    st.write("AI 會像學生背考古題一樣，把這檔標的過去一年的技術指標全部背下來，然後預測明天它是漲還是跌！(純供參考，不代表一定會中)")
                if st.button("🧠 叫 AI 預測明天漲跌", type="primary"):
                    df_ai = load_data(target_stock, period="1y")
                    if not df_ai.empty:
                        prob_up, importance = run_ai_prediction(df_ai)
                        if prob_up is not None: st.plotly_chart(plot_ml_prediction(prob_up, importance), use_container_width=True)
            
            with tabH:
                st.markdown(f"### 💰 資金控管建議：我該買幾張？")
                with st.expander("📖 為什麼這功能是散戶救星？", expanded=True):
                    st.write("「全押」是散戶破產的主因！真正的贏家會先問：「這筆如果看錯，我最多只能賠多少？」\n這個計算機會看這檔標的近期的『脾氣（震盪幅度）』，幫你算出**最安全、就算停損也不會痛的買進張數**。")

                df_pos = load_data(target_stock, period="3mo")
                if df_pos is not None and not df_pos.empty and len(df_pos) > 15:
                    prev_close = df_pos['Close'].shift(1)
                    tr = pd.concat([df_pos['High'] - df_pos['Low'], (df_pos['High'] - prev_close).abs(), (df_pos['Low'] - prev_close).abs()], axis=1).max(axis=1)
                    atr_14 = tr.rolling(window=14).mean().iloc[-1]
                    latest_close = df_pos['Close'].iloc[-1]

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        user_capital = st.number_input("💵 你準備拿多少錢出來投資這檔？", min_value=10000, value=500000, step=50000)
                    with c2:
                        risk_tolerance = st.slider("⚠️ 萬一買錯，你最多願意賠掉本金的幾 %？", 0.5, 5.0, 2.0, 0.5, help="華爾街鐵律：單筆虧損絕對不要超過總本金的 2%！")
                    with c3:
                        atr_multiplier = st.slider("📏 停損要設多寬 (預設2倍震盪)", 1.0, 5.0, 2.0, 0.5, help="倍數越大，越不容易被主力洗出場，但能買的數量就會變少。")

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

                        st.markdown("#### 🎯 AI 精算安全方案")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("目前的價格", f"${latest_close:.2f}")
                        m2.metric("跌到這價位就逃命", f"${stop_loss_price:.2f}", f"-{stop_loss_dist:.2f} (跌 {(stop_loss_dist/latest_close*100):.1f}%)", delta_color="inverse")
                        m3.metric("💡 系統建議買進股數", f"{recommended_shares:,} 股", f"約等於 {recommended_shares/1000:.1f} 張")
                        m4.metric("總共需要花費", f"${actual_invest_amount:,.0f}", f"佔你的總本金 {(actual_invest_amount/user_capital*100):.1f}%")

                        st.success(f"> **💡 戰略分析：** 如果你照著建議買了 **{recommended_shares:,} 股**，就算明天運氣極差，崩盤觸發了逃命價 **${stop_loss_price:.2f}**，你也只會損失大約 **${int(max_loss_amount):,}**。這完美控制在你規定的 **{risk_tolerance}%** 虧損紅線內，這就是長期致富的秘訣！")

    elif page == "🌍 投資組合回測 (多檔)":
        st.markdown("## 🌍 幫整個清單做大回測")
        with st.expander("📖 這是做什麼的？", expanded=True):
            st.write("前面的回測是一檔一檔測，這個引擎是**拿一筆總資金，讓系統自動在你的『觀察名單』裡到處尋找獵物買賣**！這最接近真實法人的量化基金操作方式。")
            
        if not st.session_state.watchlist:
            st.warning("⚠️ 你的觀察名單是空的，請先去左側新增標的，系統才有東西可以測！")
            return

        strategy_dict_port = {
            'ma_cross': '1️⃣ 均線交叉 (長線)', 'macd_cross': '2️⃣ MACD (爆發)',
            'rsi_reversion': '3️⃣ RSI (抄底)', 'bb_breakout': '4️⃣ 布林通道 (突破)', 'combined': '5️⃣ 👑 終極多因子'
        }
        inv_strategy_dict_port = {v: k for k, v in strategy_dict_port.items()}
        selected_strategy_name_port = st.selectbox("🧠 基金核心策略", list(inv_strategy_dict_port.keys()))
        selected_strategy_port = inv_strategy_dict_port[selected_strategy_name_port]

        c1, c2, c3 = st.columns(3)
        with c1: port_cap = st.number_input("💰 基金總規模", min_value=100000, value=1000000, step=100000)
        with c2: short_ma_p = st.number_input("短均線", min_value=3, value=5, step=1, key='p_s')
        with c3: long_ma_p = st.number_input("長均線", min_value=10, value=20, step=1, key='p_l')

        f1, f2, f3 = st.columns(3)
        with f1: use_filter_p = st.checkbox("🛡️ 啟動 60MA 熊市保護傘", value=True, key='p_f')
        with f2: allow_short_p = st.checkbox("🐻 允許基金放空", value=False, key='p_sh')
        with f3: max_alloc = st.slider("單檔標的最高只能佔用總資金的比例", 0.1, 1.0, 0.2, 0.1, help="避免雞蛋放在同一個籃子裡")
        
        use_atr_p = st.checkbox("🛡️ 啟用 ATR 動態防護網", value=True, key='p_atr')
        if use_atr_p:
            a1, a2, a3 = st.columns(3)
            with a1: risk_pct_p = st.number_input("單筆風險 (%)", value=2.0, step=0.5, key='p_r')
            with a2: atr_sl_p = st.number_input("停損 (x ATR)", value=2.0, step=0.5, key='p_sl')
            with a3: atr_tp_p = st.number_input("停利 (x ATR)", value=4.0, step=0.5, key='p_tp')
        else:
            risk_pct_p, atr_sl_p, atr_tp_p = 2.0, 2.0, 4.0
            
        st.markdown("---")
        if st.button("🌍 啟動基金歷史回測", type="primary", use_container_width=True):
            with st.spinner(f"正在掃描所有清單，執行交叉運算..."):
                data_dict = {}
                for tk in st.session_state.watchlist:
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
                        st.markdown("#### 📊 虛擬基金戰報")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("兩年後總資金變為", f"${int(metrics['Final Equity']):,}")
                        m2.metric("兩年總獲利率", f"{metrics['ROI (%)']:.1f}%")
                        m3.metric("出手機會與勝率", f"{metrics['Win Rate (%)']:.1f}%", f"總共交易了 {metrics['Total Trades']} 次")
                        m4.metric("期間最大跌幅", f"{metrics['Max Drawdown (%)']:.1f}%")
                        st.plotly_chart(plot_equity_curve(eq_df, title='🌍 基金資金累積曲線'), use_container_width=True)
                        if not tr_df.empty: 
                            st.write("📜 **基金歷史交易明細：**")
                            render_dataframe(tr_df, hide_index=True)

if __name__ == "__main__":
    setup_page() 
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        
    if not st.session_state.logged_in:
        auth_page()
    else:
        main_app()