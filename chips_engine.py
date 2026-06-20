import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from FinMind.data import DataLoader
import datetime

@st.cache_data(ttl=3600 * 4) 
def fetch_stock_chips(stock_id, token=""):
    """抓取個股三大法人每日買賣超數據 (已內建 FinMind VIP 金鑰支援)"""
    try:
        dl = DataLoader()
        if token:
            dl.login_by_token(api_token=token.strip())

        # 去除 Yahoo Finance 的 .TW 後綴，轉換成 FinMind 看得懂的純數字代號
        clean_id = stock_id.replace(".TW", "").replace(".TWO", "")
        
        # 自動推算過去 60 天
        start_date = (datetime.date.today() - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
        
        df = dl.taiwan_stock_institutional_investors(stock_id=clean_id, start_date=start_date)
        
        if df is None or df.empty:
            return pd.DataFrame({"error": ["近期無法人買賣超資料，或 API 拒絕連線"]})
        
        if 'buy' not in df.columns or 'sell' not in df.columns or 'name' not in df.columns:
            return pd.DataFrame({"error": [f"API 回傳異常，找不到買賣超欄位。回傳內容: {', '.join(df.columns)}"]})

        # 強制將買賣股數轉為數字，並計算淨買賣超 (買 - 賣)
        df['buy'] = pd.to_numeric(df['buy'], errors='coerce').fillna(0)
        df['sell'] = pd.to_numeric(df['sell'], errors='coerce').fillna(0)
        df['Net'] = df['buy'] - df['sell']

        # 🌟 智慧分類：將 FinMind 複雜的英文名稱歸納為「三大法人」
        def map_name(name):
            name = str(name).lower()
            if 'foreign' in name or '外資' in name: return '外資'
            elif 'investment' in name or '投信' in name: return '投信'
            elif 'dealer' in name or '自營' in name: return '自營商'
            else: return '其他'

        df['Entity'] = df['name'].apply(map_name)
        df = df[df['Entity'] != '其他']

        # 將「股數」轉換為台灣人習慣的「張數」 (1 張 = 1000 股)
        df['Net_Shares'] = df['Net'] / 1000
        
        # 將同一天、同一個法人的多筆紀錄加總 (例如自營商有分避險跟自行買賣，我們把它合在一起)
        grouped = df.groupby(['date', 'Entity'], as_index=False)['Net_Shares'].sum()
        
        return grouped

    except Exception as e:
        return pd.DataFrame({"error": [f"系統例外錯誤: {str(e)}"]})

def plot_institutional_chips(df, stock_id):
    """繪製三大法人買賣超直覺柱狀圖"""
    if df is None or df.empty or "error" in df.columns:
        fig = go.Figure()
        error_msg = df['error'].iloc[0] if ("error" in df.columns and len(df) > 0) else "未知的 API 錯誤"
        fig.add_annotation(
            text=f"⚠️ 暫停獲取籌碼資料<br><span style='font-size:14px; color:#FFA15A;'>請確認 FinMind 金鑰或 API 狀態<br>({error_msg})</span>", 
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#FF4B4B")
        )
        fig.update_layout(
            title=dict(text=f'🏦 {stock_id} 三大法人買賣超', font=dict(size=22, color="#E0E0E0")),
            height=450, template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis_visible=False, yaxis_visible=False
        )
        return fig

    fig = go.Figure()
    
    # 幫三大法人配上專屬的亮眼顏色
    colors = {'外資': '#19D3F3', '投信': '#FF4B4B', '自營商': '#FFA15A'}
    
    # 分別將外資、投信、自營商畫到圖表上
    for entity in ['外資', '投信', '自營商']:
        entity_df = df[df['Entity'] == entity]
        if not entity_df.empty:
            fig.add_trace(go.Bar(
                x=entity_df['date'], 
                y=entity_df['Net_Shares'],
                name=entity,
                marker_color=colors[entity]
            ))

    fig.update_layout(
        title=dict(text=f'🏦 {stock_id} 三大法人買賣超趨勢 (單位: 張)', font=dict(size=22, color="#E0E0E0")),
        height=450, template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        barmode='group', # 🌟 並排顯示，讓你一眼看出誰在買誰在賣
        font=dict(color='#E0E0E0'), margin=dict(l=50, r=50, b=50, t=50),
        hovermode='x unified', hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="#FFFFFF"), bordercolor="#333333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14, color="white"))
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    return fig