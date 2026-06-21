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
    """👑 V2.0 旗艦版：千人千面多因子分類掃描引擎"""
    if not watchlist: 
        return False, "⚠️ 觀察名單是空的，系統無股票可掃描。"
        
    # 準備分類清單
    bullish_list = []
    bearish_list = []
    neutral_list = []
    
    for tk in watchlist:
        df = load_data(tk, period="6mo")
        if df is None or len(df) < 60: 
            continue
            
        df = calculate_scanner_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        close_price = last['Close']
        ma20 = last['MA20']
        
        # 🚀 核心邏輯：多因子自動分群
        if strategy == 'combined':
            # 🟢 強勢買進邏輯：站上月線 + MACD多頭 + RSI強勢
            if close_price > ma20 and last['MACD'] > last['MACD_Signal'] and last['RSI_14'] > 50:
                bullish_list.append({
                    "tk": tk, "price": close_price, 
                    "reason": "站上 20 日生命線、MACD 翻轉向上、RSI 突破 50 多空線。",
                    "stop_loss": ma20 # 自動以月線作為防守價
                })
            # 🔴 轉弱警告邏輯：跌破月線 + MACD空頭
            elif close_price < ma20 and last['MACD'] < last['MACD_Signal']:
                bearish_list.append({
                    "tk": tk, "price": close_price, 
                    "reason": "跌破 20 日生命線，MACD 動能轉弱，請注意風險。"
                })
            # ⚪ 其餘盤整
            else:
                neutral_list.append(tk)
        else:
            # 兼容其他單一策略，若觸發則放入強勢區
            signal = None
            if strategy == 'ma_cross' and prev['Close'] < prev['MA20'] and close_price > ma20:
                signal = "股價突破月線 (買進訊號)"
            elif strategy == 'macd_cross' and prev['MACD'] < prev['MACD_Signal'] and last['MACD'] > last['MACD_Signal']:
                signal = "MACD 柱狀圖翻紅 (動能轉強)"
            elif strategy == 'rsi_reversion' and prev['RSI_14'] < 30 and last['RSI_14'] >= 30:
                signal = "RSI 超賣區抄底反彈"
            elif strategy == 'bb_breakout' and prev['Close'] < prev['BB_Upper'] and close_price > last['BB_Upper']:
                signal = "突破布林通道上軌 (打開天花板)"
                
            if signal:
                bullish_list.append({"tk": tk, "price": close_price, "reason": signal, "stop_loss": ma20})
            else:
                neutral_list.append(tk)

    # 🎨 組合 V2.0 旗艦版 HTML 推播文字
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg_lines = [
        f"🤖 <b>華爾街量化終端機 - 每日盤後雷達</b>",
        f"📅 掃描時間：{now_str}",
        f"🔍 您的專屬名單共掃描：{len(watchlist)} 檔標的",
        f"🎯 使用策略：👑 多因子複合濾網",
        ""
    ]
    
    if bullish_list:
        msg_lines.append("🟢 <b>【強勢買進 / 突破訊號】</b>")
        for item in bullish_list:
            msg_lines.append(f"🏷️ <b>{item['tk']}</b>")
            msg_lines.append(f"💵 最新股價：${item['price']:.2f}")
            msg_lines.append(f"📈 觸發條件：{item['reason']}")
            msg_lines.append(f"🛡️ 建議防守價 (月線)：${item['stop_loss']:.2f}\n")
            
    if bearish_list:
        msg_lines.append("🔴 <b>【危險警告 / 轉弱訊號】</b>")
        for item in bearish_list:
            msg_lines.append(f"🏷️ <b>{item['tk']}</b>")
            msg_lines.append(f"💵 最新股價：${item['price']:.2f}")
            msg_lines.append(f"📉 觸發條件：{item['reason']}\n")
            
    if neutral_list:
        msg_lines.append("⚪ <b>【其餘觀望標的】</b>")
        neutral_str = ", ".join(neutral_list)
        msg_lines.append(f"目前無特殊訊號：{neutral_str}\n")
        
    msg_lines.append("===========================")
    msg_lines.append("💡 <i>系統溫馨提醒：量化訊號僅供參考，請嚴格設定單筆風險與資金控管！</i>")

    final_msg = "\n".join(msg_lines)
    res = send_telegram_notify(token, chat_id, final_msg)
    
    if "✅" in res: 
        return True, "雷達掃描完畢，已成功推播至您的 Telegram！"
    else: 
        return False, res