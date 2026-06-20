import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from FinMind.data import DataLoader
import datetime

# 🌟 恢復快取！加入 token 作為快取鍵值的一部分
@st.cache_data(ttl=3600 * 4) 
def fetch_futures_chips(token=""):
    """抓取台指期外資未平倉數據 (正式上線版)"""
    try:
        dl = DataLoader()
        
        if token:
            clean_token = token.strip()
            dl.login_by_token(api_token=clean_token)
            
        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime('%Y-%m-%d')
        df = dl.taiwan_futures_institutional_investors(start_date=start_date)
        
        if df is None or df.empty:
            return pd.DataFrame({"error": ["API完全無回應"]})
            
        if 'name' not in df.columns:
            raw_msg = str(df.to_dict(orient='records')[0])
            return pd.DataFrame({"error": [f"API 拒絕連線！伺服器原話: {raw_msg}"]})

        df = df[df['name'].str.contains('Foreign|外資', na=False, case=False)]
        
        if 'commodity_id' in df.columns:
            df = df[df['commodity_id'].str.contains('TX', na=False)]
            
        if df.empty:
            return pd.DataFrame({"error": ["查無大台指外資數據"]})

        long_cols = [c for c in df.columns if 'long' in c.lower() and 'open_interest' in c.lower() and 'amount' not in c.lower()]
        short_cols = [c for c in df.columns if 'short' in c.lower() and 'open_interest' in c.lower() and 'amount' not in c.lower()]
        
        if not long_cols or not short_cols:
             return pd.DataFrame({"error": ["API 欄位變更，找不到多空數據"]})

        long_col_name = long_cols[0]
        short_col_name = short_cols[0]

        df[long_col_name] = pd.to_numeric(df[long_col_name], errors='coerce').fillna(0)
        df[short_col_name] = pd.to_numeric(df[short_col_name], errors='coerce').fillna(0)
        
        df['Net_Open_Interest'] = df[long_col_name] - df[short_col_name]
        df = df.groupby('date', as_index=False)['Net_Open_Interest'].sum()
        
        return df.tail(20)
    except Exception as e:
        return pd.DataFrame({"error": [f"系統例外錯誤: {str(e)}"]})

def plot_futures_chart(df):
    """繪製外資期貨淨未平倉趨勢圖"""
    if df is None or df.empty or "error" in df.columns:
        fig = go.Figure()
        error_msg = df['error'].iloc[0] if ("error" in df.columns and len(df) > 0) else "未知的 API 錯誤"

        fig.add_annotation(
            text=f"⚠️ 暫停獲取 FinMind 籌碼資料<br><span style='font-size:14px; color:#FFA15A;'>請確認側邊欄的 FinMind Token<br>({error_msg})</span>", 
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#FF4B4B")
        )
        fig.update_layout(
            title=dict(text='🛡️ 外資台指期淨未平倉波段監控', font=dict(size=22, color="#E0E0E0")),
            height=450, template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis_visible=False, yaxis_visible=False
        )
        return fig
        
    fig = go.Figure()
    
    net_oi = pd.to_numeric(df['Net_Open_Interest'], errors='coerce').fillna(0)
    fig.add_trace(go.Bar(
        x=df['date'], y=net_oi,
        marker_color=['#FF4B4B' if val < 0 else '#00CC96' for val in net_oi],
        name='外資淨未平倉口數'
    ))
    
    fig.update_layout(
        title=dict(text='🛡️ 外資台指期淨未平倉波段監控 (紅: 空單避險 / 綠: 多單加碼)', font=dict(size=22, color="#E0E0E0")),
        height=450, template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'), margin=dict(l=50, r=50, b=50, t=50),
        hovermode='x unified', hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="#FFFFFF"), bordercolor="#333333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14, color="white"))
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    return fig