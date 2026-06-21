import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data(ttl=3600)
def fetch_macro_data(period="1y"):
    """抓取台灣大盤與全球總經數據 (加入雙重保險與防彈機制)"""
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
            
    # 🛡️ 第一層保險：如果 Yahoo 漏抓了大盤 (^TWII)，自動改用 0050 替代
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
        
        # 🛡️ 第二層保險：確保 4 個欄位一定存在，缺少的就塞入 None，防止畫圖當機
        for col in ["TAIEX", "USD_TWD", "US_10Y", "VIX"]:
            if col not in macro_df.columns:
                macro_df[col] = None 
                
        return macro_df
        
    return pd.DataFrame()

def plot_macro_dashboard(df):
    """繪製專業的總經四重聯動對比圖 (防彈強化版)"""
    
    # 🛡️ 第三層保險：如果完全沒有網路或沒有數據，回傳一個空圖表，保護系統不崩潰
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="⚠️ 總經數據暫時無法載入，請稍後再試", template='plotly_dark')
        return fig

    # 建立 4 個子圖的框架，共用 X 軸 (時間)
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            "📈 台灣加權指數 / 0050 (TAIEX)", 
            "💵 美元/台幣匯率 (向上代表台幣貶值、外資撤出)", 
            "🏦 美國 10 年期公債殖利率 (全球資金成本)", 
            "😨 VIX 恐慌指數 (市場情緒)"
        )
    )

    # 🛡️ 終極防彈畫圖：使用 df.get('欄位') 代替 df['欄位']，找不到也不會報錯！
    fig.add_trace(go.Scatter(x=df.index, y=df.get('TAIEX'), line=dict(color='#00CC96', width=2), name='大盤指數'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('USD_TWD'), line=dict(color='#FFA15A', width=2), name='USD/TWD'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('US_10Y'), line=dict(color='#19D3F3', width=2), name='US 10Y Yield(%)'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.get('VIX'), line=dict(color='#FF4B4B', width=2), name='VIX', fill='tozeroy', fillcolor='rgba(255, 75, 75, 0.1)'), row=4, col=1)

    # 🌟 介面最佳化設定
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