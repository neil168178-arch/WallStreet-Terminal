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
    """判斷是否為 ETF (代號為 00 開頭，或包含英文字母如 00900B)"""
    if not ticker: return False
    tk = ticker.split('.')[0]
    if tk.startswith('00') or not tk.isdigit(): return True
    return False

# ==========================================
# 📡 基礎發送與舊版存摺監控模組
# ==========================================
def send_telegram_notify(token, chat_id, message):
    """將文字訊號發送至您的 Telegram 手機 APP"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML" 
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            return "✅ Telegram 機器人連線成功！推播已發送。"
        else:
            return f"❌ 失敗：{res.text}"
    except Exception as e:
        return f"❌ 錯誤：網路連線異常 {e}"

def calculate_scanner_indicators(df):
    """🌟 雷達專屬的指標計算引擎"""
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
    """👑 V2.1 旗艦版：新增【異常標的防呆回報】機制"""
    print("🚨🚨🚨 報告總部：我現在正在執行 V2.1 旗艦版程式碼 (包含異常回報)！！！ 🚨🚨🚨")
    
    if not watchlist: 
        return False, "⚠️ 觀察名單是空的，系統無股票可掃描。"
        
    bullish_list, bearish_list, neutral_list = [], [], []
    error_list = [] 
    
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
                bullish_list.append({"tk": tk, "price": close_price, "reason": "站上 20 日生命線、MACD 翻轉向上、RSI 突破 50 多空線。", "stop_loss": ma20})
            elif close_price < ma20 and last['MACD'] < last['MACD_Signal']:
                bearish_list.append({"tk": tk, "price": close_price, "reason": "跌破 20 日生命線，MACD 動能轉弱，請注意風險。"})
            else:
                neutral_list.append(tk)
        else:
            signal = None
            if strategy == 'ma_cross' and prev['Close'] < prev['MA20'] and close_price > ma20: signal = "股價突破月線 (買進訊號)"
            elif strategy == 'macd_cross' and prev['MACD'] < prev['MACD_Signal'] and last['MACD'] > last['MACD_Signal']: signal = "MACD 柱狀圖翻紅 (動能轉強)"
            elif strategy == 'rsi_reversion' and prev['RSI_14'] < 30 and last['RSI_14'] >= 30: signal = "RSI 超賣區抄底反彈"
            elif strategy == 'bb_breakout' and prev['Close'] < prev['BB_Upper'] and close_price > last['BB_Upper']: signal = "突破布林通道上軌 (打開天花板)"
            if signal: bullish_list.append({"tk": tk, "price": close_price, "reason": signal, "stop_loss": ma20})
            else: neutral_list.append(tk)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg_lines = [f"🤖 <b>華爾街量化終端機 - 每日盤後雷達</b>", f"📅 掃描時間：{now_str}", f"🔍 您的專屬名單共掃描：{len(watchlist)} 檔標的", f"🎯 使用策略：👑 多因子複合濾網", ""]
    
    if bullish_list:
        msg_lines.append("🟢 <b>【強勢買進 / 突破訊號】</b>")
        for item in bullish_list: msg_lines.extend([f"🏷️ <b>{item['tk']}</b>", f"💵 最新股價：${item['price']:.2f}", f"📈 觸發條件：{item['reason']}", f"🛡️ 建議防守價 (月線)：${item['stop_loss']:.2f}\n"])
    if bearish_list:
        msg_lines.append("🔴 <b>【危險警告 / 轉弱訊號】</b>")
        for item in bearish_list: msg_lines.extend([f"🏷️ <b>{item['tk']}</b>", f"💵 最新股價：${item['price']:.2f}", f"📉 觸發條件：{item['reason']}\n"])
    if neutral_list:
        msg_lines.extend(["⚪ <b>【其餘觀望標的】</b>", f"目前無特殊訊號：{', '.join(neutral_list)}\n"])
        
    if error_list:
        msg_lines.extend(["⚠️ <b>【資料不足 / 異常標的】</b>", f"因上市未滿60天或代號無效，略過掃描：{', '.join(error_list)}\n"])
        
    msg_lines.extend(["===========================", "💡 <i>系統溫馨提醒：量化訊號僅供參考，請嚴格設定單筆風險與資金控管！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, "成功推播") if "✅" in res else (False, res)

# =========================================================================
# 🚀 任務 1 全新引擎：全市場掃描「平民強勢股 (150元內)」並推播
# =========================================================================
def get_twse_civilian_candidates():
    candidates = []
    names = {}
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10).json()
        for item in res:
            try:
                price = float(item.get('ClosingPrice', 0))
                vol = float(item.get('TradeVolume', 0)) / 1000 
                if 0 < price <= 150 and vol >= 2000:
                    ticker = f"{item['Code']}.TW"
                    candidates.append(ticker)
                    names[ticker] = item['Name']
            except: continue
    except Exception as e:
        print(f"證交所 API 獲取失敗: {e}")
    return candidates, names

def run_civilian_strong_scanner(token, chat_id):
    if not token or not chat_id: return False, "⚠️ 尚未設定 Telegram 金鑰！"

    candidates, names_dict = get_twse_civilian_candidates()
    if not candidates: return False, "⚠️ 找不到符合初步條件的標的，或證交所 API 維護中。"

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
                        "代號": ticker.replace('.TW', ''),
                        "名稱": names_dict.get(ticker, ""),
                        "股價": current_price,
                        "5日漲幅": return_5d,
                        "月線狀態": "✅ 站上 20MA"
                    }
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(check_technical, candidates):
            if res: strong_stocks.append(res)

    strong_stocks = sorted(strong_stocks, key=lambda x: x["5日漲幅"], reverse=True)[:15] # 放寬至15檔供分類
    now_str = datetime.now().strftime("%Y-%m-%d")

    if not strong_stocks:
        msg = f"📊 <b>本日量化雷達報告 ({now_str})</b>\n\n今日市場震盪，無符合「平民強勢股」條件之標的。"
        res = send_telegram_notify(token, chat_id, msg)
        return (True, "掃描完成，今日無符合標的已回報 TG。") if "✅" in res else (False, res)

    # 🌟 神級優化：將結果分為 ETF 與 個股 兩大陣營
    etf_list = [s for s in strong_stocks if is_etf_ticker(s['代號'])]
    stock_list = [s for s in strong_stocks if not is_etf_ticker(s['代號'])]

    msg_lines = [
        f"🚀 <b>華爾街量化終端機：平民強勢股日報</b>",
        f"📅 日期：{now_str}",
        f"🎯 濾網：150元內 | 2000張以上 | 站上月線 | 近5日漲幅>3%\n"
    ]
    
    if etf_list:
        msg_lines.append("📊 <b>【強勢 ETF 專區】(存股避險)</b>")
        for i, s in enumerate(etf_list, 1):
            msg_lines.extend([
                f"<b>{i}. {s['名稱']} ({s['代號']})</b>",
                f"   • 股價：${s['股價']:.2f} | 🔥 動能：{s['5日漲幅']:.1f}%\n"
            ])

    if stock_list:
        msg_lines.append("🔥 <b>【強勢個股 專區】(波段爆發)</b>")
        for i, s in enumerate(stock_list, 1):
            msg_lines.extend([
                f"<b>{i}. {s['名稱']} ({s['代號']})</b>",
                f"   • 股價：${s['股價']:.2f} | 🔥 動能：{s['5日漲幅']:.1f}%\n"
            ])

    msg_lines.extend(["===========================", "💡 <i>CTO 溫馨提醒：量化過濾標的僅供參考，請嚴格設定單筆風險！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, f"✅ 成功發送 {len(strong_stocks)} 檔強勢股至 Telegram！") if "✅" in res else (False, res)

# =========================================================================
# 🚀 任務 1 進階版：動態自訂條件！全市場掃描與推播
# =========================================================================
def get_twse_custom_candidates(max_price, min_vol):
    candidates = []
    names = {}
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10).json()
        for item in res:
            try:
                price = float(item.get('ClosingPrice', 0))
                vol = float(item.get('TradeVolume', 0)) / 1000 
                if 0 < price <= max_price and vol >= min_vol:
                    ticker = f"{item['Code']}.TW"
                    candidates.append(ticker)
                    names[ticker] = item['Name']
            except: continue
    except Exception as e:
        print(f"證交所 API 獲取失敗: {e}")
    return candidates, names

def run_custom_strong_scanner(token, chat_id, max_price, min_vol, min_daily_change, min_5d_change):
    if not token or not chat_id: return False, "⚠️ 尚未設定 Telegram 金鑰！"

    candidates, names_dict = get_twse_custom_candidates(max_price, min_vol)
    if not candidates: return False, "⚠️ 找不到符合您價格與成交量條件的標的。"

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
                
                if (current_price <= max_price and 
                    daily_change >= min_daily_change and 
                    return_5d >= min_5d_change):
                    return {
                        "代號": ticker.replace('.TW', ''),
                        "名稱": names_dict.get(ticker, ""),
                        "股價": current_price,
                        "今日漲幅": daily_change,
                        "5日漲幅": return_5d
                    }
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(check_technical, candidates):
            if res: strong_stocks.append(res)

    strong_stocks = sorted(strong_stocks, key=lambda x: x["今日漲幅"], reverse=True)[:15]
    now_str = datetime.now().strftime("%Y-%m-%d")

    if not strong_stocks:
        msg = f"📊 <b>自訂條件雷達報告 ({now_str})</b>\n\n依據您的嚴格條件，今日無符合標的。"
        res = send_telegram_notify(token, chat_id, msg)
        return (True, "掃描完成，無符合標的已回報 TG。") if "✅" in res else (False, res)

    # 🌟 神級優化：將客製化結果也分為 ETF 與 個股 兩大陣營
    etf_list = [s for s in strong_stocks if is_etf_ticker(s['代號'])]
    stock_list = [s for s in strong_stocks if not is_etf_ticker(s['代號'])]

    msg_lines = [
        f"🚀 <b>華爾街量化終端機：自訂強勢股推播</b>",
        f"📅 日期：{now_str}",
        f"🎯 濾網：{max_price}元內 | {min_vol}張以上 | 日起伏>{min_daily_change}% | 5日累積>{min_5d_change}%\n"
    ]
    
    if etf_list:
        msg_lines.append("📊 <b>【客製化 ETF 專區】</b>")
        for i, s in enumerate(etf_list, 1):
            trend_emoji = "🔥" if s['今日漲幅'] > 0 else ("🧊" if s['今日漲幅'] < 0 else "➖")
            msg_lines.extend([
                f"<b>{i}. {s['名稱']} ({s['代號']})</b>",
                f"   • 股價：${s['股價']:.2f} | 起伏：{trend_emoji} {s['今日漲幅']:.2f}%\n"
            ])

    if stock_list:
        msg_lines.append("🔥 <b>【客製化個股 專區】</b>")
        for i, s in enumerate(stock_list, 1):
            trend_emoji = "🔥" if s['今日漲幅'] > 0 else ("🧊" if s['今日漲幅'] < 0 else "➖")
            msg_lines.extend([
                f"<b>{i}. {s['名稱']} ({s['代號']})</b>",
                f"   • 股價：${s['股價']:.2f} | 起伏：{trend_emoji} {s['今日漲幅']:.2f}%\n"
            ])

    msg_lines.extend(["===========================", "💡 <i>站長專屬客製化雷達掃描完畢，祝您操作順利！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, f"✅ 成功發送 {len(strong_stocks)} 檔客製化飆股至 Telegram！") if "✅" in res else (False, res)