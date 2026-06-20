import streamlit as st
import yfinance as yf

@st.cache_data(ttl=3600) # 快取 1 小時自動更新
def load_data(stock_id, period):
    """從 yfinance 獲取歷史股票數據"""
    stock = yf.Ticker(stock_id)
    df = stock.history(period=period)
    return df