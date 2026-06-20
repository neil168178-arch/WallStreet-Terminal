import pandas as pd
import numpy as np
import ta

def add_indicators(df):
    """為歷史數據加上技術指標 (SMA, RSI, MACD, Bollinger Bands)"""
    if df is None or df.empty: return df
    df = df.copy()
    
    # 均線 (多加一條 60MA 作為長線多空濾網)
    df['MA5'] = ta.trend.sma_indicator(df['Close'], window=5)
    df['MA20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['MA60'] = ta.trend.sma_indicator(df['Close'], window=60)
    
    # RSI
    df['RSI_14'] = ta.momentum.rsi(df['Close'], window=14)
    
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD_12_26_9'] = macd.macd()
    df['MACDs_12_26_9'] = macd.macd_signal()
    df['MACDh_12_26_9'] = macd.macd_diff()
    
    # 布林通道
    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['BBU_20_2.0'] = bb.bollinger_hband()
    df['BBL_20_2.0'] = bb.bollinger_lband()
    
    return df

def run_backtest(df, strategy_type='ma_cross', fee_rate=0.001425, tax_rate=0.003, fee_discount=0.6):
    """
    執行多種技術指標策略回測，並自動扣除台股真實交易成本
    strategy_type 支援: 'ma_cross', 'macd_cross', 'rsi_reversion', 'bb_breakout', 'combined'
    """
    if df is None or df.empty: return df, {}
    df = df.copy()
    
    # 確保指標已計算 (防呆機制)
    if 'MA5' not in df.columns:
        df = add_indicators(df)
        
    # ==========================================
    # 🌟 核心升級一：支援 5 種不同的策略邏輯
    # ==========================================
    if strategy_type == 'ma_cross':
        # 策略 1：傳統均線黃金交叉
        df['Signal'] = np.where(df['MA5'] > df['MA20'], 1, 0)
        
    elif strategy_type == 'macd_cross':
        # 策略 2：動能策略 (MACD 柱狀圖翻正 且 站上 20MA 才做多)
        df['Signal'] = np.where((df['MACDh_12_26_9'] > 0) & (df['Close'] > df['MA20']), 1, 0)
        
    elif strategy_type == 'rsi_reversion':
        # 策略 3：RSI 抄底策略 (向量化狀態機寫法)
        # 邏輯：RSI < 30 買進，RSI > 70 賣出平倉
        df['Buy_Sig'] = np.where(df['RSI_14'] < 30, 1, 0)
        df['Sell_Sig'] = np.where(df['RSI_14'] > 70, -1, 0)
        df['Signal'] = df['Buy_Sig'] + df['Sell_Sig']
        # ffill() 會讓訊號延續：買進後保持 1，直到遇到 -1 變成 0
        df['Signal'] = df['Signal'].replace(0, np.nan).ffill().replace(-1, 0).fillna(0)
        
    elif strategy_type == 'bb_breakout':
        # 策略 4：布林突破策略
        # 邏輯：收盤價突破上軌買進，跌破中軌 (MA20) 賣出
        df['Buy_Sig'] = np.where(df['Close'] > df['BBU_20_2.0'], 1, 0)
        df['Sell_Sig'] = np.where(df['Close'] < df['MA20'], -1, 0)
        df['Signal'] = df['Buy_Sig'] + df['Sell_Sig']
        df['Signal'] = df['Signal'].replace(0, np.nan).ffill().replace(-1, 0).fillna(0)
        
    elif strategy_type == 'combined':
        # 策略 5：機構級多因子濾網 (MACD黃金交叉 + RSI大於50 + 股價在季線60MA之上)
        df['Signal'] = np.where((df['MACDh_12_26_9'] > 0) & (df['RSI_14'] > 50) & (df['Close'] > df['MA60']), 1, 0)
        
    else:
        df['Signal'] = 0 # 預設無動作

    # ==========================================
    # 完美保留你的交易成本與淨利計算邏輯
    # ==========================================
    df['Position'] = df['Signal'].shift(1).fillna(0)
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Gross_Return'] = df['Position'] * df['Market_Return']
    
    df['Trade_Diff'] = df['Position'].diff().fillna(0)
    buy_friction = np.where(df['Trade_Diff'] == 1, fee_rate * fee_discount, 0)
    sell_friction = np.where(df['Trade_Diff'] == -1, (fee_rate * fee_discount) + tax_rate, 0)
    total_friction = buy_friction + sell_friction
    
    df['Strategy_Net_Return'] = df['Strategy_Gross_Return'] - total_friction
    
    df['大盤累計報酬'] = (1 + df['Market_Return']).cumprod()
    df['策略(扣除成本前)'] = (1 + df['Strategy_Gross_Return']).cumprod()
    df['策略(扣除成本後真實報酬)'] = (1 + df['Strategy_Net_Return']).cumprod()
    
    # ==========================================
    # 🌟 核心升級二：產生戰報數據
    # ==========================================
    metrics = calculate_metrics(df)
    
    return df, metrics

def calculate_metrics(df):
    """計算回測核心績效指標 (KPI)"""
    if df.empty or '策略(扣除成本後真實報酬)' not in df.columns: return {}
    
    # 1. 總報酬率
    total_return = (df['策略(扣除成本後真實報酬)'].iloc[-1] - 1) * 100
    market_return = (df['大盤累計報酬'].iloc[-1] - 1) * 100
    
    # 2. 計算最大回撤 (Max Drawdown)
    cum_ret = df['策略(扣除成本後真實報酬)']
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / running_max
    max_dd = drawdown.min() * 100
    
    # 3. 交易次數
    total_trades = len(df[df['Trade_Diff'] == -1]) # 計算賣出次數等於完整交易次數
    
    # 4. 持倉日勝率 (有持倉的日子裡，賺錢天數的比例)
    win_days = len(df[(df['Position'] == 1) & (df['Strategy_Net_Return'] > 0)])
    loss_days = len(df[(df['Position'] == 1) & (df['Strategy_Net_Return'] < 0)])
    win_rate = (win_days / (win_days + loss_days) * 100) if (win_days + loss_days) > 0 else 0

    return {
        "總報酬率 (%)": round(total_return, 2),
        "大盤報酬率 (%)": round(market_return, 2),
        "最大回撤 (%)": round(max_dd, 2),
        "總交易次數": total_trades,
        "持倉日勝率 (%)": round(win_rate, 2)
    }