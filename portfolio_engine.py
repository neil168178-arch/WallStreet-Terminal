import pandas as pd
import yfinance as yf
import streamlit as st
import numpy as np

@st.cache_data(ttl=60) # 股價每 60 秒快取一次即可
def calculate_portfolio_pnl(portfolio_df, fee_discount):
    """
    計算投資組合的真實未實現損益，自動扣除台灣券商手續費與證交稅
    """
    results = []
    
    for _, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = pd.to_numeric(row["持股數量(股)"], errors='coerce')
        cost = pd.to_numeric(row["總投資成本(元)"], errors='coerce')
        
        # 如果沒有持股或資料異常，就跳過
        if pd.isna(shares) or pd.isna(cost) or shares <= 0:
            continue
            
        try:
            # 透過 yfinance 抓取即時報價 (fast_info 速度最快)
            stock = yf.Ticker(ticker)
            current_price = stock.fast_info['lastPrice']
        except Exception as e:
            print(f"無法抓取 {ticker} 報價: {e}")
            current_price = np.nan
            
        if pd.isna(current_price):
            continue
            
        # 1. 計算目前總市值
        market_value = current_price * shares
        
        # 2. 計算預估賣出手續費 (0.1425% * 折扣，且最低收 20 元)
        raw_fee = market_value * 0.001425 * fee_discount
        sell_fee = max(20, int(raw_fee))
        
        # 3. 計算預估證交稅 (ETF 0.1%, 一般股票 0.3%)
        # 台股 ETF 通常代號為 00 開頭 (例如 0050, 00878)
        tax_rate = 0.001 if ticker.startswith('00') else 0.003
        sell_tax = int(market_value * tax_rate)
        
        # 4. 計算真實未實現損益 (市值 - 原始成本 - 賣出手續費 - 賣出證交稅)
        net_value = market_value - sell_fee - sell_tax
        net_profit = net_value - cost
        
        # 計算報酬率
        roi_percent = (net_profit / cost) * 100 if cost > 0 else 0
        
        results.append({
            "股票代號": ticker,
            "持股數量": int(shares),
            "最新報價": round(current_price, 2),
            "總投資成本": int(cost),
            "目前總市值": int(market_value),
            "賣出手續費": sell_fee,
            "賣出證交稅": sell_tax,
            "未實現損益": int(net_profit),
            "報酬率(%)": round(roi_percent, 2)
        })
        
    return pd.DataFrame(results)