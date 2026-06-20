import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data(ttl=3600)
def fetch_macro_data(period="1y"):
    """抓取台灣大盤與全球總體經濟核心數據 (修復跨國時區與假日錯位 Bug)"""
    tickers = {
        "TAIEX": "^TWII",  # 台灣加權指數
        "USD_TWD": "TWD=X", # 美元/台幣匯率
        "US_10Y": "^TNX",   # 美國 10 年期公債殖利率
        "VIX": "^VIX"       # 芝加哥選擇權交易所 VIX 恐慌指數
    }
    
    df_dict = {}
    for name, ticker in tickers.items():
        try:
            # 抓取歷史數據，只取收盤價
            data = yf.Ticker(ticker).history(period=period)
            if not data.empty:
                # 強制拔除時區，並將時間歸零
                data.index = pd.to_datetime(data.index).tz_localize(None).normalize()
                df_dict[name] = data['Close']
        except Exception as e:
            print(f"抓取總經數據 {name} 失敗: {e}")
            pass
            
    if df_dict:
        # 將所有序列合併成一個大的 DataFrame
        macro_df = pd.DataFrame(df_dict)
        
        # 處理各國國定假日不同的問題
        macro_df.ffill(inplace=True)
        
        # 把最前面可能還是無法對齊的殘餘空值刪除，確保圖表乾淨
        macro_df.dropna(inplace=True)
        return macro_df
        
    return pd.DataFrame()

def plot_macro_dashboard(df):
    """繪製專業的總經四重聯動對比圖"""
    # 建立 4 個子圖的框架，共用 X 軸 (時間)
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            "📈 台灣加權指數 (TAIEX)", 
            "💵 美元/台幣匯率 (向上代表台幣貶值、外資撤出)", 
            "🏦 美國 10 年期公債殖利率 (全球資金成本)", 
            "😨 VIX 恐慌指數 (市場情緒)"
        )
    )

    # 1. 台股大盤
    fig.add_trace(go.Scatter(x=df.index, y=df['TAIEX'], line=dict(color='#00CC96', width=2), name='加權指數'), row=1, col=1)
    
    # 2. 匯率
    fig.add_trace(go.Scatter(x=df.index, y=df['USD_TWD'], line=dict(color='#FFA15A', width=2), name='USD/TWD'), row=2, col=1)
    
    # 3. 公債殖利率
    fig.add_trace(go.Scatter(x=df.index, y=df['US_10Y'], line=dict(color='#19D3F3', width=2), name='US 10Y Yield(%)'), row=3, col=1)
    
    # 4. VIX (使用紅色漸層填滿，因為數字飆高代表危險)
    fig.add_trace(go.Scatter(x=df.index, y=df['VIX'], line=dict(color='#FF4B4B', width=2), name='VIX', fill='tozeroy', fillcolor='rgba(255, 75, 75, 0.1)'), row=4, col=1)

    # 🌟 介面最佳化設定 (強制透明背景與白字，抵抗 Streamlit 預設主題)
    fig.update_layout(
        height=850,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',  # 🌟 強制整個圖表外框透明
        plot_bgcolor='rgba(0,0,0,0)',   # 🌟 強制繪圖區背景透明
        font=dict(color='#E0E0E0'),     # 🌟 強制全局基礎字體為雪白
        margin=dict(l=50, r=50, b=50, t=50),
        hovermode='x unified',
        showlegend=False
    )
    
    # 🌟 強制 X 軸與 Y 軸的刻度與格線顏色
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    # 隱藏六日的空白斷層
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    
    # 將四個子圖的標題也變成白色
    for annotation in fig['layout']['annotations']: 
        annotation['font'] = dict(size=14, color='#E0E0E0')
        
    return fig