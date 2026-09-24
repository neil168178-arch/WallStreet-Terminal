import requests
import pandas as pd
import numpy as np
from datetime import datetime
from data_engine import load_data
import yfinance as yf
import concurrent.futures

# ==========================================
# 🧠 系統底層：標的智能分類器 
# ==========================================
def is_etf_ticker(ticker):
    if not ticker: return False
    tk = ticker.split('.')[0]
    if tk.startswith('00') or not tk.isdigit(): return True
    return False

# ==========================================
# 📡 基礎發送與舊版存摺監控模組 (每日專屬雷達)
# ==========================================
def send_telegram_notify(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200: return "✅ Telegram 機器人連線成功！推播已發送。"
        else: return f"❌ 失敗：{res.text}"
    except Exception as e:
        return f"❌ 錯誤：網路連線異常 {e}"

def calculate_scanner_indicators(df):
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
    std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std * 2)
    df['BB_Lower'] = df['MA20'] - (std * 2)
    return df

def run_daily_signal_scanner(watchlist, strategy, token, chat_id):
    if not watchlist: return False, "⚠️ 觀察名單是空的，系統無標的可掃描。"
    bullish_list, bearish_list, neutral_list, error_list = [], [], [], []
    for tk in watchlist:
        df = load_data(tk, period="6mo")
        if df is None or len(df) < 60: 
            error_list.append(tk)
            continue
        df = calculate_scanner_indicators(df)
        last, prev = df.iloc[-1], df.iloc[-2]
        close_price, ma20 = last['Close'], last['MA20']
        if strategy == 'combined':
            if close_price > ma20 and last['MACD'] > last['MACD_Signal'] and last['RSI_14'] > 50:
                bullish_list.append({"tk": tk, "price": close_price, "reason": "站上 20 日線、MACD 向上、RSI > 50", "stop_loss": ma20})
            elif close_price < ma20 and last['MACD'] < last['MACD_Signal']:
                bearish_list.append({"tk": tk, "price": close_price, "reason": "跌破 20 日線，MACD 轉弱"})
            else:
                neutral_list.append(tk)
        else:
            signal = None
            if strategy == 'ma_cross' and prev['Close'] < prev['MA20'] and close_price > ma20: signal = "突破月線"
            elif strategy == 'macd_cross' and prev['MACD'] < prev['MACD_Signal'] and last['MACD'] > last['MACD_Signal']: signal = "MACD 翻紅"
            elif strategy == 'rsi_reversion' and prev['RSI_14'] < 30 and last['RSI_14'] >= 30: signal = "RSI 抄底"
            elif strategy == 'bb_breakout' and prev['Close'] < prev['BB_Upper'] and close_price > last['BB_Upper']: signal = "突破布林上軌"
            if signal: bullish_list.append({"tk": tk, "price": close_price, "reason": signal, "stop_loss": ma20})
            else: neutral_list.append(tk)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg_lines = [f"🤖 <b>華爾街量化終端機 - 每日盤後雷達</b>", f"📅 掃描時間：{now_str}", f"🔍 掃描數量：{len(watchlist)} 檔標的\n"]
    if bullish_list:
        msg_lines.append("🟢 <b>【強勢買進 / 突破訊號】</b>")
        for item in bullish_list: msg_lines.extend([f"🏷️ <b>{item['tk']}</b>", f"💵 股價：${item['price']:.2f} | 📈 {item['reason']}\n"])
    if bearish_list:
        msg_lines.append("🔴 <b>【危險警告 / 轉弱訊號】</b>")
        for item in bearish_list: msg_lines.extend([f"🏷️ <b>{item['tk']}</b>", f"💵 股價：${item['price']:.2f} | 📉 {item['reason']}\n"])
    if neutral_list: msg_lines.extend(["⚪ <b>【觀望標的】</b>", f"{', '.join(neutral_list)}\n"])
    if error_list: msg_lines.extend(["⚠️ <b>【異常標的】</b>", f"略過掃描：{', '.join(error_list)}\n"])
    msg_lines.append("💡 <i>系統溫馨提醒：量化訊號僅供參考！</i>")
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, "成功推播") if "✅" in res else (False, res)

# =========================================================================
# 🚀 任務 1：全市場發射台 (預設 + 自訂條件)
# =========================================================================
def get_twse_candidates(max_price, min_vol, is_etf_mode):
    candidates = []
    names = {}
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10).json()
        for item in res:
            try:
                price = float(item.get('ClosingPrice', 0))
                vol = float(item.get('TradeVolume', 0)) / 1000 
                ticker = f"{item['Code']}.TW"
                if is_etf_ticker(ticker) != is_etf_mode: continue
                if 0 < price <= max_price and vol >= min_vol:
                    candidates.append(ticker)
                    names[ticker] = item['Name']
            except: continue
    except Exception as e: print(f"證交所 API 獲取失敗: {e}")
    return candidates, names

def run_civilian_strong_scanner(token, chat_id, is_etf_mode):
    if not token or not chat_id: return False, "⚠️ 尚未設定 Telegram 金鑰！"
    sys_name = "ETF" if is_etf_mode else "個股"
    candidates, names_dict = get_twse_candidates(max_price=150, min_vol=2000, is_etf_mode=is_etf_mode)
    if not candidates: return False, f"⚠️ 找不到符合初步條件的平民 {sys_name}。"
    candidates = candidates[:150]
    strong_stocks = []

    def check_technical(ticker):
        try:
            hist = yf.Ticker(ticker).history(period="2mo") 
            if len(hist) >= 20:
                close_prices = hist['Close']
                current_price = close_prices.iloc[-1]
                price_5d_ago = close_prices.iloc[-6] if len(close_prices) >= 6 else close_prices.iloc[0]
                ma20 = close_prices.rolling(window=20).mean().iloc[-1]
                return_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                if current_price > ma20 and return_5d >= 3.0 and current_price <= 150:
                    return {
                        "代號": ticker.replace('.TW', ''), "名稱": names_dict.get(ticker, ""),
                        "股價": current_price, "5日漲幅": return_5d, "月線狀態": "✅ 站上 20MA"
                    }
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(check_technical, candidates):
            if res: strong_stocks.append(res)

    strong_stocks = sorted(strong_stocks, key=lambda x: x["5日漲幅"], reverse=True)[:10]
    now_str = datetime.now().strftime("%Y-%m-%d")

    if not strong_stocks:
        msg = f"📊 <b>本日量化雷達 ({now_str})</b>\n\n今日無符合「平民強勢」條件之 {sys_name}。"
        res = send_telegram_notify(token, chat_id, msg)
        return (True, "無標的已回報") if "✅" in res else (False, res)

    msg_lines = [
        f"🚀 <b>華爾街終端機：平民強勢 {sys_name} 日報</b>",
        f"📅 日期：{now_str}",
        f"🎯 濾網：150元內 | 2000張以上 | 站上月線 | 5日漲幅>3%\n"
    ]
    for i, s in enumerate(strong_stocks, 1):
        msg_lines.extend([f"<b>{i}. {s['名稱']} ({s['代號']})</b>", f"   • 股價：${s['股價']:.2f} | 🔥 動能：{s['5日漲幅']:.1f}%\n"])
    msg_lines.extend(["===========================", f"💡 <i>專屬 {sys_name} 雷達掃描完畢！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, f"✅ 成功發送 {len(strong_stocks)} 檔強勢 {sys_name}！") if "✅" in res else (False, res)

def run_custom_strong_scanner(token, chat_id, max_price, min_vol, min_daily_change, min_5d_change, is_etf_mode):
    if not token or not chat_id: return False, "⚠️ 尚未設定 Telegram 金鑰！"
    sys_name = "ETF" if is_etf_mode else "個股"
    candidates, names_dict = get_twse_candidates(max_price, min_vol, is_etf_mode)
    if not candidates: return False, f"⚠️ 找不到符合條件的 {sys_name}。"
    candidates = candidates[:150]
    strong_stocks = []

    def check_technical(ticker):
        try:
            hist = yf.Ticker(ticker).history(period="10d")
            if len(hist) >= 6:
                close_prices = hist['Close']
                current_price = close_prices.iloc[-1]
                prev_price = close_prices.iloc[-2]
                price_5d_ago = close_prices.iloc[-6]
                daily_change = ((current_price - prev_price) / prev_price) * 100
                return_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                if (current_price <= max_price and daily_change >= min_daily_change and return_5d >= min_5d_change):
                    return {
                        "代號": ticker.replace('.TW', ''), "名稱": names_dict.get(ticker, ""),
                        "股價": current_price, "今日漲幅": daily_change, "5日漲幅": return_5d
                    }
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(check_technical, candidates):
            if res: strong_stocks.append(res)

    strong_stocks = sorted(strong_stocks, key=lambda x: x["今日漲幅"], reverse=True)[:15]
    now_str = datetime.now().strftime("%Y-%m-%d")

    if not strong_stocks:
        msg = f"📊 <b>自訂條件雷達 ({now_str})</b>\n\n依據嚴格條件，今日無符合之 {sys_name}。"
        res = send_telegram_notify(token, chat_id, msg)
        return (True, "無標的已回報") if "✅" in res else (False, res)

    msg_lines = [
        f"🚀 <b>華爾街終端機：自訂強勢 {sys_name} 推播</b>",
        f"📅 日期：{now_str}",
        f"🎯 濾網：{max_price}元內 | {min_vol}張以上 | 日起伏>{min_daily_change}% | 5日累積>{min_5d_change}%\n"
    ]
    for i, s in enumerate(strong_stocks, 1):
        trend_emoji = "🔥" if s['今日漲幅'] > 0 else ("🧊" if s['今日漲幅'] < 0 else "➖")
        msg_lines.extend([f"<b>{i}. {s['名稱']} ({s['代號']})</b>", f"   • 股價：${s['股價']:.2f} | 起伏：{trend_emoji} {s['今日漲幅']:.2f}%\n"])
    msg_lines.extend(["===========================", f"💡 <i>專屬客製化 {sys_name} 雷達掃描完畢！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, f"✅ 成功發送客製化 {sys_name}！") if "✅" in res else (False, res)

# =========================================================================
# 🚀 任務 2：明日之星預測引擎 (尋找剛出現黃金交叉的 10 大標的) 🌟【全新補上】
# =========================================================================
def run_tomorrow_recommendation_scanner(token, chat_id, is_etf_mode):
    if not token or not chat_id: return False, "⚠️ 尚未設定 Telegram 金鑰！"
    sys_name = "ETF" if is_etf_mode else "個股"
    candidates, names_dict = get_twse_candidates(max_price=150, min_vol=2000, is_etf_mode=is_etf_mode)
    if not candidates: return False, f"⚠️ 找不到符合條件的平民 {sys_name}。"

    candidates = candidates[:150]
    tomorrow_stars = []

    def predict_momentum(ticker):
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if len(hist) >= 20:
                df = hist.copy()
                df['MA20'] = df['Close'].rolling(window=20).mean()
                exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = exp1 - exp2
                df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
                
                last = df.iloc[-1]
                prev = df.iloc[-2]
                
                if (last['Close'] > last['MA20'] and last['MACD_Hist'] > 0 and last['MACD_Hist'] > prev['MACD_Hist']):
                    return {
                        "代號": ticker.replace('.TW', ''), "名稱": names_dict.get(ticker, ""),
                        "股價": last['Close'], "動能爆發力": (last['MACD_Hist'] / last['Close']) * 100
                    }
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(predict_momentum, candidates):
            if res: tomorrow_stars.append(res)

    tomorrow_stars = sorted(tomorrow_stars, key=lambda x: x["動能爆發力"], reverse=True)[:10]
    now_str = datetime.now().strftime("%Y-%m-%d")

    if not tomorrow_stars:
        msg = f"🔮 <b>明日推薦預測 ({now_str})</b>\n\n今日無明顯發動跡象的 {sys_name}。"
        res = send_telegram_notify(token, chat_id, msg)
        return (True, "預測完成，無標的已回報") if "✅" in res else (False, res)

    msg_lines = [
        f"🔮 <b>華爾街終端機：明日十大潛力 {sys_name}</b>",
        f"📅 日期：{now_str}",
        f"🎯 邏輯：主力點火 | MACD 發散 | 站上月線\n"
    ]
    for i, s in enumerate(tomorrow_stars, 1):
        msg_lines.extend([f"<b>{i}. {s['名稱']} ({s['代號']})</b>", f"   • 收盤價：${s['股價']:.2f} | ⚡ 推薦原因：MACD 動能噴出\n"])
    msg_lines.extend(["===========================", f"💡 <i>CTO 溫馨提醒：請於明日開盤觀察是否延續氣勢！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, f"✅ 成功發送 {len(tomorrow_stars)} 檔潛力 {sys_name}！") if "✅" in res else (False, res)