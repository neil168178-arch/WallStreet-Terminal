import requests
import pandas as pd
import numpy as np
from data_engine import load_data

def send_telegram_notify(token, chat_id, message):
    """將文字訊號發送至您的 Telegram 手機 APP"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML" # 支援 HTML 標籤，讓推播文字更漂亮
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
    """🌟 雷達專屬的指標計算引擎：保證欄位名稱絕對精準，永遠不會再有 KeyError！"""
    df = df.copy()
    
    # 1. 均線 (MA20)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # 2. MACD 與訊號線
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 3. RSI_14
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    # 4. 布林通道 (Bollinger Bands)
    std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std * 2)
    df['BB_Lower'] = df['MA20'] - (std * 2)
    
    return df

def run_daily_signal_scanner(watchlist, strategy, token, chat_id):
    """掃描名單內的股票，若觸發策略則透過 TG 推播"""
    if not watchlist: 
        return False, "⚠️ 觀察名單是空的，系統無股票可掃描。"
        
    msg_lines = [f"🤖 <b>華爾街量化終端機：盤後雷達</b>", f"🔍 掃描策略：{strategy}", "--------------------------"]
    has_signal = False
    
    for tk in watchlist:
        df = load_data(tk, period="6mo")
        if df is None or len(df) < 60: 
            continue
            
        # 🌟 呼叫專屬計算引擎，確保 MACD, RSI, MA20 等欄位絕對存在
        df = calculate_scanner_indicators(df)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        signal = None
        # 盤後雷達的策略邏輯
        if strategy == 'ma_cross':
            if prev['Close'] < prev['MA20'] and last['Close'] > last['MA20']: 
                signal = "🟢 股價突破月線 (買進訊號)"
        elif strategy == 'macd_cross':
            if prev['MACD'] < prev['MACD_Signal'] and last['MACD'] > last['MACD_Signal']: 
                signal = "🔥 MACD 柱狀圖翻紅 (動能轉強)"
        elif strategy == 'rsi_reversion':
            if prev['RSI_14'] < 30 and last['RSI_14'] >= 30: 
                signal = "🚀 RSI 超賣區抄底反彈"
        elif strategy == 'bb_breakout':
            if prev['Close'] < prev['BB_Upper'] and last['Close'] > last['BB_Upper']: 
                signal = "📈 突破布林通道上軌 (打開天花板)"
        elif strategy == 'combined':
            if last['Close'] > last['MA20'] and last['MACD'] > last['MACD_Signal'] and last['RSI_14'] > 50:
                signal = "👑 多因子共振，趨勢完美噴出！"

        if signal:
            has_signal = True
            msg_lines.append(f"• <b>{tk}</b>: {signal}")
            msg_lines.append(f"  └ 收盤價: ${last['Close']:.2f}")
            
    if not has_signal:
        msg_lines.append("<i>今日全市場平靜，無觸發訊號。請好好休息！☕</i>")
        
    final_msg = "\n".join(msg_lines)
    res = send_telegram_notify(token, chat_id, final_msg)
    
    if "✅" in res: 
        return True, "雷達掃描完畢，已成功推播至您的 Telegram！"
    else: 
        return False, res