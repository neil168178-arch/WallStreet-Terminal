import requests
import pandas as pd
import numpy as np
from datetime import datetime
from data_engine import load_data

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
    # 👇👇👇 竊聽器升級！ 👇👇👇
    print("🚨🚨🚨 報告總部：我現在正在執行 V2.1 旗艦版程式碼 (包含異常回報)！！！ 🚨🚨🚨")
    
    if not watchlist: 
        return False, "⚠️ 觀察名單是空的，系統無股票可掃描。"
        
    bullish_list, bearish_list, neutral_list = [], [], []
    error_list = [] # 🌟 新增：專門用來裝找不到資料或太新的 ETF / 股票
    
    for tk in watchlist:
        df = load_data(tk, period="6mo")
        
        # 🌟 攔截點：如果抓不到資料，或者上市不到 60 天，把他抓進 error_list
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
        
    # 🌟 貼心回報：把有問題的股票印在推播最下方
    if error_list:
        msg_lines.extend(["⚠️ <b>【資料不足 / 異常標的】</b>", f"因上市未滿60天或代號無效，略過掃描：{', '.join(error_list)}\n"])
        
    msg_lines.extend(["===========================", "💡 <i>系統溫馨提醒：量化訊號僅供參考，請嚴格設定單筆風險與資金控管！</i>"])
    res = send_telegram_notify(token, chat_id, "\n".join(msg_lines))
    return (True, "成功推播") if "✅" in res else (False, res)