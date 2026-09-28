import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import concurrent.futures
from datetime import datetime
from data_engine import load_data
from strategy_engine import add_indicators
from visual_engine import plot_advanced_chart
from intraday_engine import fetch_intraday_data, plot_intraday_chart
from notification_engine import send_telegram_notify

# ==========================================
# 🧠 內建智能分類與技術指標計算 (自給自足免匯入)
# ==========================================
def is_etf_ticker(ticker):
    """判斷是否為 ETF"""
    if not ticker: return False
    tk = str(ticker).split('.')[0]
    if tk.startswith('00') or not tk.isdigit(): return True
    return False

def calc_hunter_indicators(df):
    """計算強勢股所需之 MA20、MACD、RSI 指標"""
    df = df.copy()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI_14'] = 100 - (100 / (1 + rs))
    return df

# ==========================================
# 🚀 內建視覺化複合式狩獵引擎
# ==========================================
def run_visual_strong_scanner(
    is_etf_mode, max_price, min_shares, min_daily_change, 
    min_5d_change, min_vol_ratio, require_ma20, require_macd
):
    """回傳符合自訂狩獵條件的 DataFrame 供網頁視覺化呈現"""
    candidates = []
    names_dict = {}
    raw_vols = {}
    
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10).json()
        for item in res:
            try:
                price = float(item.get('ClosingPrice', 0))
                shares = float(item.get('TradeVolume', 0))
                ticker = f"{item['Code']}.TW"
                
                # 1. 嚴格分流：個股 vs ETF
                if is_etf_ticker(ticker) != is_etf_mode:
                    continue
                # 2. 初步過濾：股價與最低成交股數
                if 0 < price <= max_price and shares >= min_shares:
                    candidates.append(ticker)
                    names_dict[ticker] = item['Name']
                    raw_vols[ticker] = int(shares)
            except:
                continue
    except Exception as e:
        print(f"證交所 API 獲取失敗: {e}")
        return pd.DataFrame()

    if not candidates:
        return pd.DataFrame()

    # 依成交量排序，取前 120 檔最活絡標的進行深度技術運算
    candidates = sorted(candidates, key=lambda x: raw_vols.get(x, 0), reverse=True)[:120]
    results_list = []

    def analyze_hunter_target(ticker):
        try:
            hist = yf.Ticker(ticker).history(period="2mo")
            if len(hist) >= 20:
                df = calc_hunter_indicators(hist)
                close_prices = df['Close']
                volumes = df['Volume']
                
                last = df.iloc[-1]
                prev = df.iloc[-2]
                price_5d_ago = close_prices.iloc[-6] if len(close_prices) >= 6 else close_prices.iloc[0]
                
                current_price = float(last['Close'])
                if current_price > max_price:
                    return None
                
                daily_change = ((current_price - float(prev['Close'])) / float(prev['Close'])) * 100
                return_5d = ((current_price - float(price_5d_ago)) / float(price_5d_ago)) * 100
                
                # 計算爆量倍數 (今日量 ÷ 前5日均量)
                avg_vol_5d = volumes.iloc[-6:-1].mean()
                vol_ratio = (float(last['Volume']) / avg_vol_5d) if avg_vol_5d > 0 else 1.0
                
                # 計算 MACD 柱狀圖動能
                macd_hist_last = float(last['MACD'] - last['MACD_Signal'])
                macd_hist_prev = float(prev['MACD'] - prev['MACD_Signal'])
                
                # 核對數值濾網
                if daily_change < min_daily_change or return_5d < min_5d_change or vol_ratio < min_vol_ratio:
                    return None
                # 核對技術面開關
                if require_ma20 and current_price <= float(last['MA20']):
                    return None
                if require_macd and not (macd_hist_last > 0 and macd_hist_last > macd_hist_prev):
                    return None
                
                # 抓取近 10 日收盤價作為迷你走勢圖數據
                sparkline = [round(float(x), 2) for x in close_prices.tail(10).tolist()]
                rsi_val = float(last['RSI_14']) if pd.notna(last['RSI_14']) else 50.0
                shares_count = raw_vols.get(ticker, int(last['Volume']))
                
                return {
                    "➕ 選取": False,
                    "代號": ticker.replace('.TW', ''),
                    "名稱": names_dict.get(ticker, ""),
                    "股價": round(current_price, 2),
                    "今日起伏(%)": round(daily_change, 2),
                    "5日漲幅(%)": round(return_5d, 2),
                    "💥 爆量倍數": round(vol_ratio, 2),
                    "成交量(股)": shares_count,
                    "成交量(張)": int(shares_count // 1000),
                    "🔥 動能強度": int(min(max(rsi_val, 0), 100)),
                    "📈 近期走勢": sparkline
                }
        except:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(analyze_hunter_target, candidates):
            if res:
                results_list.append(res)

    if not results_list:
        return pd.DataFrame()

    df_out = pd.DataFrame(results_list)
    return df_out.sort_values(by="今日起伏(%)", ascending=False).reset_index(drop=True)


# ==========================================
# 🖥️ 第三核心：強勢飆股與 ETF 視覺化狩獵大廳 UI
# ==========================================
def render_strong_system(add_to_watchlist_fn, tg_token, tg_chat_id, mobile_config):
    """🔥 第三核心：強勢飆股與 ETF 視覺化狩獵大廳"""
    
    if 'strong_df_cache' not in st.session_state:
        st.session_state.strong_df_cache = pd.DataFrame()
    if 'strong_last_update' not in st.session_state:
        st.session_state.strong_last_update = "尚未掃描 (請點擊下方按鈕啟動)"

    # 頂部狀態列與強制刷新按鈕
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.markdown("## 🔥 強勢標的視覺化狩獵中心")
        st.caption(f"🕒 最後數據更新時間：**{st.session_state.strong_last_update}** (支援零延遲快取操作)")
    with col_btn:
        if st.button("🔄 手動更新全部資訊", type="secondary", use_container_width=True, help="清除快取並重新抓取最新報價"):
            st.cache_data.clear()
            st.session_state.strong_last_update = f"{datetime.now().strftime('%H:%M:%S')} (已清空快取)"
            st.toast("🔄 全站快取已清空！請點擊啟動掃描獲取最新盤況。", icon="✅")
            st.rerun()

    st.markdown("---")

    # 第一區：🎛️ 複合式狩獵控制台
    st.markdown("### 🎛️ 第一區：複合式狩獵控制台")
    
    c_mode1, c_mode2, c_mode3 = st.columns(3)
    with c_mode1:
        target_universe = st.radio("🎯 1. 選擇掃描宇宙 (嚴格分流)", ["📈 強勢個股", "📊 強勢 ETF"], horizontal=True)
        scan_is_etf = (target_universe == "📊 強勢 ETF")
        u_name = "ETF" if scan_is_etf else "個股"
    with c_mode2:
        preset_mode = st.selectbox(
            f"⚡ 2. 快速策略預設 ({u_name})", 
            [f"📡 平民強勢 {u_name} (預設)", f"🔮 明日 10 大潛力 {u_name} (MACD點火)", f"🛠️ 完全自訂條件 {u_name}"]
        )
    with c_mode3:
        vol_unit = st.radio("🌱 3. 成交量單位 (學生/主力切換)", ["🌱 零股模式 (單位：股)", "📦 整張模式 (單位：張)"], horizontal=True)
        is_odd_lot = ("零股" in vol_unit)

    default_price = 150
    default_5d = 3.0 if "平民強勢" in preset_mode else -10.0
    default_ma20 = True
    default_macd = True if "明日 10 大潛力" in preset_mode else False

    with st.expander("⚙️ 展開微調：股價、零股/整張成交量、爆量倍數與技術濾網", expanded=("完全自訂" in preset_mode)):
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            max_price = st.number_input("💰 股價最高上限 (元)", min_value=10, max_value=3000, value=default_price, step=10)
        with p2:
            if is_odd_lot:
                min_vol_input = st.number_input("🌱 最低成交股數 (零股)", min_value=1000, max_value=50000000, value=500000, step=50000)
                min_shares = min_vol_input
            else:
                min_vol_input = st.number_input("📦 最低成交張數 (整張)", min_value=10, max_value=50000, value=2000, step=500)
                min_shares = min_vol_input * 1000
        with p3:
            min_daily = st.number_input("⚡ 今日起伏大於 (%)", min_value=-10.0, max_value=10.0, value=0.0, step=0.5)
        with p4:
            min_5d = st.number_input("📈 近5日累積漲幅大於 (%)", min_value=-30.0, max_value=50.0, value=default_5d, step=1.0)

        t1, t2, t3 = st.columns(3)
        with t1:
            min_vol_ratio = st.slider("💥 爆量倍數門檻 (今量 ÷ 5日均量)", 0.5, 5.0, 1.0, 0.1)
        with t2:
            req_ma20 = st.checkbox("🛡️ 股價必須站上 20MA (月線保護)", value=default_ma20)
        with t3:
            req_macd = st.checkbox("🔮 MACD 柱狀圖翻紅放大 (明日點火)", value=default_macd)

    if st.button(f"🚀 啟動全市場【{u_name}】獵人掃描", type="primary", use_container_width=True):
        with st.spinner(f"🌍 正在連線證交所與 Yahoo 財經，依條件過濾全市場 {u_name}... (約需 10-15 秒)"):
            df_res = run_visual_strong_scanner(
                is_etf_mode=scan_is_etf, max_price=max_price, min_shares=min_shares,
                min_daily_change=min_daily, min_5d_change=min_5d, min_vol_ratio=min_vol_ratio,
                require_ma20=req_ma20, require_macd=req_macd
            )
            st.session_state.strong_df_cache = df_res
            st.session_state.strong_last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if df_res.empty:
                st.warning(f"⚠️ 在目前的嚴格條件下，找不到符合的 {u_name}，請嘗試放寬拉桿條件！")
            else:
                st.success(f"🎉 掃描完成！共抓出 {len(df_res)} 檔強勢 {u_name}！")

    # 第二區：📋 視覺化飆股尋寶牆 (打勾入庫 + 同步推播)
    df_show = st.session_state.strong_df_cache
    if not df_show.empty:
        st.markdown("---")
        st.markdown(f"### 📋 第二區：強勢{u_name}即時尋寶牆 (打勾即可存入名單)")
        
        vol_col_to_hide = "成交量(張)" if is_odd_lot else "成交量(股)"
        display_cols = [c for c in df_show.columns if c != vol_col_to_hide]

        edited_df = st.data_editor(
            df_show[display_cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "➕ 選取": st.column_config.CheckboxColumn("➕ 選取", help="打勾後點擊下方按鈕即可加入雲端觀察名單", default=False),
                "🔥 動能強度": st.column_config.ProgressColumn("🔥 動能強度 (RSI)", min_value=0, max_value=100, format="%d"),
                "📈 近期走勢": st.column_config.LineChartColumn("📈 近10日走勢", width="medium")
            },
            disabled=[c for c in display_cols if c != "➕ 選取"]
        )

        act1, act2 = st.columns(2)
        with act1:
            if st.button(f"➕ 將勾選標的存入【{u_name}】雲端名單", use_container_width=True):
                selected_rows = edited_df[edited_df["➕ 選取"] == True]
                if selected_rows.empty:
                    st.warning("⚠️ 請先在表格最左側將喜歡的標的「打勾」！")
                else:
                    target_watchlist = st.session_state.etf_watchlist if scan_is_etf else st.session_state.stock_watchlist
                    for _, r in selected_rows.iterrows():
                        full_tk = f"{r['代號']}.TW"
                        if full_tk not in target_watchlist:
                            add_to_watchlist_fn(full_tk, scan_is_etf)
                    st.success(f"✅ 已將勾選的標的同步寫入 Supabase 雲端名單！")

        with act2:
            if st.button("✈️ 將上方表格結果一鍵推播至 Telegram", type="secondary", use_container_width=True):
                if not tg_token or not tg_chat_id:
                    st.warning("⚠️ 請先在左側邊欄輸入並儲存 Telegram Token 與 Chat ID！")
                else:
                    msg_lines = [
                        f"🔥 <b>華爾街終端機：強勢{u_name}狩獵清單</b>",
                        f"🕒 更新時間：{st.session_state.strong_last_update}\n"
                    ]
                    for i, r in edited_df.head(12).iterrows():
                        vol_str = f"{r['成交量(股)']:,}股" if is_odd_lot else f"{r['成交量(張)']:,}張"
                        msg_lines.extend([
                            f"<b>{i+1}. {r['名稱']} ({r['代號']})</b>",
                            f"   • 股價：${r['股價']:.2f} ({r['今日起伏(%)']:+.2f}%) | 💥爆量：{r['💥 爆量倍數']}倍 ({vol_str})\n"
                        ])
                    res = send_telegram_notify(tg_token, tg_chat_id, "\n".join(msg_lines))
                    if "✅" in res:
                        st.success(res)
                        st.balloons()
                    else:
                        st.error(res)

        # 第三區：🎯 同頁極速狙擊鏡 (K線 + 心電圖 + 學生零股 ATR 試算)
        st.markdown("---")
        st.markdown("### 🎯 第三區：同頁極速狙擊鏡 (免切換分頁直接透視)")
        
        options = [f"{r['代號']}.TW - {r['名稱']}" for _, r in df_show.iterrows()]
        selected_option = st.selectbox("🔍 點選上方任一檔強勢標的，立即展開技術大圖與零股停損試算：", options)
        
        if selected_option:
            sniper_tk = selected_option.split(" - ")[0]
            tab_k, tab_intra, tab_atr = st.tabs(["📈 技術看盤畫布 (K線)", "⚡ 今日盤中心電圖", "💰 學生/獵人零股 ATR 資金控管"])
            
            with tab_k:
                df_tech = load_data(sniper_tk, period="6mo")
                if df_tech is not None and not df_tech.empty:
                    st.plotly_chart(plot_advanced_chart(add_indicators(df_tech), sniper_tk), use_container_width=True, config=mobile_config)
                    
            with tab_intra:
                df_in, in_name = fetch_intraday_data(sniper_tk)
                if df_in is not None and not df_in.empty:
                    st.plotly_chart(plot_intraday_chart(df_in, sniper_tk, in_name), use_container_width=True, config=mobile_config)
                    
            with tab_atr:
                st.markdown(f"#### 🌱 專為學生零股族與短線獵人設計的保命計算機 ({sniper_tk})")
                df_pos = load_data(sniper_tk, period="3mo")
                if df_pos is not None and not df_pos.empty and len(df_pos) > 15:
                    prev_close = df_pos['Close'].shift(1)
                    tr = pd.concat([df_pos['High'] - df_pos['Low'], (df_pos['High'] - prev_close).abs(), (df_pos['Low'] - prev_close).abs()], axis=1).max(axis=1)
                    atr_14 = float(tr.rolling(window=14).mean().iloc[-1])
                    latest_close = float(df_pos['Close'].iloc[-1])

                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        user_cap = st.number_input("💵 預計投入總預算 (元，支援千元小資)", min_value=1000, value=10000, step=1000)
                    with sc2:
                        risk_tol = st.slider("⚠️ 單筆最大可承受虧損 (%)", 0.5, 5.0, 2.0, 0.5)
                    with sc3:
                        atr_mult = st.slider("📏 停損安全距離 (x ATR)", 1.0, 4.0, 2.0, 0.5)

                    max_loss_amt = user_cap * (risk_tol / 100.0)
                    sl_dist = atr_14 * atr_mult
                    sl_price = latest_close - sl_dist

                    if sl_dist > 0:
                        rec_shares = int(max_loss_amt / sl_dist)
                        cost_amt = rec_shares * latest_close
                        if cost_amt > user_cap:
                            rec_shares = int(user_cap / latest_close)
                            cost_amt = rec_shares * latest_close

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("目前最新股價", f"${latest_close:.2f}")
                        m2.metric("🛑 跌破逃命價位", f"${sl_price:.2f}")
                        m3.metric("🌱 建議買進零股數", f"{rec_shares:,} 股", f"約 {rec_shares/1000:.2f} 張")
                        m4.metric("💰 實際動用資金", f"${cost_amt:,.0f}")
                        st.info(f"💡 **小資戰略分析**：用 **${user_cap:,}** 預算買進 **{rec_shares:,} 股（零股）**，萬一跌破 **${sl_price:.2f}** 停損出場，您最多只會賠掉約 **${int(rec_shares * sl_dist):,} 元**，完美保護本金！")