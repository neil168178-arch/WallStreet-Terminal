import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from crawler_engine import load_tw_stock_names

# 🌟 極短線快取：設定為 60 秒，確保資料夠「即時」，又不會因為頻繁重整被 API 封鎖
@st.cache_data(ttl=60) 
def fetch_intraday_data(stock_id):
    """抓取今日 1 分鐘級別的極短線即時數據"""
    try:
        stock = yf.Ticker(stock_id)
        # interval="1m" 代表抓取 1 分鐘 K 線，period="1d" 代表只抓今天
        df = stock.history(period="1d", interval="1m")
        
        if df.empty:
            return pd.DataFrame(), "未知名稱"
            
        # 轉換時間格式並去掉時區，讓畫面更乾淨
        df.index = pd.to_datetime(df.index).tz_localize(None)
        
        # 🌟 華爾街當沖神器：計算 VWAP (成交量加權平均價)
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (df['Volume'] * typical_price).cumsum() / df['Volume'].cumsum()
        
        # 從我們的智慧字典獲取中文名稱
        name_map = load_tw_stock_names()
        clean_id = stock_id.replace(".TW", "").replace(".TWO", "")
        company_name = name_map.get(clean_id, stock_id)
        
        return df, company_name
    except Exception as e:
        print(f"即時數據抓取失敗: {e}")
        return pd.DataFrame(), "未知名稱"

def plot_intraday_chart(df, stock_id, company_name):
    """繪製專業的即時閃電圖與 VWAP 當沖監控線 (台股動態變色版)"""
    fig = go.Figure()

    # 動態判斷漲跌顏色 (台股: 紅漲綠跌)
    open_price = df['Open'].iloc[0]
    current_price = df['Close'].iloc[-1]
    
    if current_price >= open_price:
        line_color = '#FF4B4B'
        fill_color = 'rgba(255, 75, 75, 0.1)'
    else:
        line_color = '#00CC96'
        fill_color = 'rgba(0, 204, 150, 0.1)'

    # 1. 閃電圖
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Close'],
        mode='lines',
        line=dict(color=line_color, width=2.5),
        fill='tozeroy',
        fillcolor=fill_color,
        name='即時走勢'
    ))

    # 2. VWAP 線
    fig.add_trace(go.Scatter(
        x=df.index, y=df['VWAP'],
        mode='lines',
        line=dict(color='#FFA15A', width=2, dash='dash'), 
        name='VWAP (當沖生命線)'
    ))

    # 對「所有折線 (Traces)」下達懸浮框字體白化的死命令
    fig.update_traces(
        hoverlabel=dict(
            bgcolor="#1E1E1E",
            bordercolor="#333333",
            font=dict(size=15, color="white")
        )
    )

    # 介面最佳化設定
    fig.update_layout(
        # 🌟 手機防護 1：縮小標題字體並鎖定位置，避免過長撞擊圖例
        title=dict(
            text=f'⚡ {company_name} ({stock_id}) - 今日即時走勢', 
            font=dict(size=18, color="#E0E0E0"),
            y=0.96, # 鎖定高度
            x=0.02
        ),
        height=550,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        
        # 🌟 手機防護 2：挑高天花板！將 t(Top) 拉高到 100，左右邊距縮小以適應手機
        margin=dict(l=15, r=15, b=50, t=100), 
        hovermode='x unified',
        
        hoverlabel=dict(
            bgcolor="#1E1E1E",       
            bordercolor="#333333",    
            font=dict(size=15, color="white") 
        ),
        
        # 🌟 手機防護 3：將圖例位置精準向上推，與標題完美錯開
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.05, 
            xanchor="right", 
            x=1,
            font=dict(size=13, color="white")
        )
    )

    fig.update_xaxes(
        tickfont=dict(color='#E0E0E0'), 
        gridcolor='rgba(255, 255, 255, 0.1)'
    )
    fig.update_yaxes(
        tickfont=dict(color='#E0E0E0'), 
        gridcolor='rgba(255, 255, 255, 0.1)'
    )

    return fig