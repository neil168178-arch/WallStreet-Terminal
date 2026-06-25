import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data(ttl=3600)
# 🌟 新增開關：帶入 is_etf_mode 參數，預設為 False (個股模式)
def fetch_macro_data(period="1y", is_etf_mode=False):
    """抓取台灣大盤與全球總經數據 (加入雙重保險與防彈機制，並支援動態切換大盤/0050)"""
    
    # 🌟 動態標的判斷：根據目前的獨立系統，決定第一張圖的基準
    main_ticker = "0050.TW" if is_etf_mode else "^TWII"
    
    tickers = {
        "TAIEX": main_ticker,  # 🤖 這裡會自動變成 0050.TW 或是 ^TWII
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
            
    # 🛡️ 原本的第一層保險：如果 Yahoo 漏抓了大盤，自動改用 0050 替代 (保留原汁原味邏輯)
    if "TAIEX" not in df_dict:
        try:
            backup_data = yf.Ticker("0050.TW").history(period=period)
            if not backup_data.empty:
                backup_data.index = pd.to_datetime(backup_data.index).tz_localize(None).normalize()
                df_dict["TAIEX"] = backup_data['Close']
        except:
            pass
            
    if df_dict:
        # 將所有序列合併成一個大的 DataFrame
        macro_df = pd.DataFrame(df_dict)
        
        # 處理各國國定假日不同的問題
        macro_df.ffill(inplace=True)
        # 把最前面可能還是無法對齊的殘餘空值刪除
        macro_df.dropna(inplace=True)
        
        # 🛡️ 原本的第二層保險：確保 4 個欄位一定存在
        for col in ["TAIEX", "USD_TWD", "US_10Y", "VIX"]:
            if col not in macro_df.columns:
                macro_df[col] = None 
                
        return macro_df
        
    return pd.DataFrame()

# 🌟 新增開關：畫圖函式也同步帶入 is_etf_mode
def plot_macro_dashboard(df, is_etf_mode=False):
    """繪製專業的總經四重聯動對比圖 (防彈強化版)"""
    
    # 🛡️ 原本的第三層保險：空數據保護
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="⚠️ 總經數據暫時無法載入，請稍後再試", template='plotly_dark')
        return fig

    # 🌟 動態決定第一個子圖的標題
    market_title = "🔵 元大台灣50 (0050) 走勢" if is_etf_mode else "🔴 台灣加權指數 (大盤) 走勢"

    # 建立 4 個子圖的框架，共用 X 軸 (時間)
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            market_title, # 🤖 套用動態變更的專業中文標題
            "💵 美元/台幣匯率 (外資撤出雷達)", 
            "🏦 美國 10 年期公債殖利率 (全球資金成本)", 
            "😨 VIX 恐慌指數 (市場情緒)"
        )
    )

    # 決定的線條顏色 (ETF 用帥氣科技藍，個股大盤用波段警戒紅)
    line_color = '#19D3F3' if is_etf_mode else '#FF4B4B'

    # 🛡️ 終極防彈畫圖：保留原有的 df.get 做法，完美抽換線條顏色
    fig.add_trace(go.Scatter(x=df.index, y=df.get('TAIEX'), line=dict(color=line_color, width=2), name='大盤/0050'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('USD_TWD'), line=dict(color='#FFA15A', width=2), name='USD/TWD'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('US_10Y'), line=dict(color='#00CC96', width=2), name='US 10Y Yield(%)'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('VIX'), line=dict(color='#FF4B4B', width=2), name='VIX', fill='tozeroy', fillcolor='rgba(255, 75, 75, 0.1)'), row=4, col=1)

    # 🌟 介面最佳化設定 (保留原本創辦人滿意的最優化參數)
    fig.update_layout(
        height=850,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',   
        plot_bgcolor='rgba(0,0,0,0)',    
        font=dict(color='#E0E0E0'),      
        margin=dict(l=50, r=50, b=50, t=50),
        hovermode='x unified',
        showlegend=False
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    
    for annotation in fig['layout']['annotations']: 
        annotation['font'] = dict(size=14, color='#E0E0E0')
        
    return fig