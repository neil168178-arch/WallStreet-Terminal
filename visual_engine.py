import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def setup_page():
    """初始化 Streamlit 頁面設定與午夜暗色系 CSS (字體與表格縮放分離版)"""
    st.set_page_config(
        page_title="專業台股看盤系統", 
        page_icon="📈", 
        layout="wide",
        initial_sidebar_state="expanded" 
    )

    custom_css = """
    <style>
        html, body, [class*="css"], .stApp {
            font-family: 'Helvetica Neue', Helvetica, Arial, 'Microsoft JhengHei', sans-serif !important;
            background-color: #0E1117 !important; 
            font-size: 18px !important;
        }
        
        [data-testid="stSidebar"] {
            background-color: #1E1E2E !important; 
        }

        /* 深色背景區塊：強制白字 */
        h1, .stApp h1, [data-testid="stMarkdownContainer"] h1, 
        h1 span, .stApp h1 span, [data-testid="stMarkdownContainer"] h1 span { 
            font-size: 35px !important; color: #FFFFFF !important; font-weight: 900 !important;  
            letter-spacing: 2px !important; padding-bottom: 1rem !important; line-height: 1.3 !important;
        }
        h2, .stApp h2, h2 span { font-size: 28px !important; color: #FAFAFA !important; }
        h3, .stApp h3, h3 span { font-size: 22px !important; color: #F5F5F5 !important; }
        
        p, span, label, li, .stMarkdown p { color: #E0E0E0 !important; }

        button[data-baseweb="tab"] div { color: #FAFAFA !important; font-weight: bold; font-size: 18px !important; }
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] div, [data-testid="stMetricValue"] span { 
            color: #FFFFFF !important; font-weight: bold; font-size: 36px !important; 
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] span { color: #BDBDBD !important; font-size: 16px !important; }
        
        /* 淺色背景區塊與按鈕：智慧動態對比 */
        .stApp input, .stApp div[data-baseweb="base-input"] { 
            background-color: #FFFFFF !important; color: #0E1117 !important; font-size: 16px !important; 
        }
        
        .stApp div[data-baseweb="select"], .stApp div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important; border-color: #CCCCCC !important; 
        }
        .stApp div[data-baseweb="select"] span, .stApp div[data-baseweb="select"] div, .stApp div[data-baseweb="select"] p {
            color: #0E1117 !important;
        }
        
        div[data-baseweb="popover"], ul[role="listbox"], ul[role="listbox"] li, ul[role="listbox"] div {
            background-color: #FFFFFF !important; 
        }
        div[data-baseweb="popover"] span, div[data-baseweb="popover"] div, div[data-baseweb="popover"] p,
        ul[role="listbox"] span, ul[role="listbox"] div, ul[role="listbox"] p { color: #0E1117 !important; }
        [data-baseweb="icon"] svg { fill: #0E1117 !important; color: #0E1117 !important; }

        div.stButton > button {
            background-color: #2A2D3E !important; border: 1px solid #4A4D5E !important; color: #FFFFFF !important;
        }
        div.stButton > button span, div.stButton > button p { color: #FFFFFF !important; font-weight: bold !important; }
        div.stButton > button:hover { background-color: #FF4B4B !important; border-color: #FF4B4B !important; }
        div.stButton > button:hover span, div.stButton > button:hover p { color: #FFFFFF !important; }
        
        [data-testid="stDataFrame"] {
            zoom: 1.05;
        }
        
        [data-testid="stHeader"] { background-color: transparent !important; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        
        @media (max-width: 768px) {
            .block-container { padding-top: 1rem; }
            h1, h1 span { font-size: 24px !important; } h2, h2 span { font-size: 20px !important; }
            h3, h3 span { font-size: 18px !important; } [data-testid="stMetricValue"], [data-testid="stMetricValue"] span { font-size: 28px !important; }
            [data-testid="stDataFrame"] { zoom: 1.0; }
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

def plot_advanced_chart(df, stock_id):
    """繪製專業 Plotly 互動式技術分析圖 (對齊閃電圖的極致視覺)"""
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    up_color, down_color = '#FF4B4B', '#00CC96' 

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color=up_color, decreasing_line_color=down_color, name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFA15A', width=1.5), name='5MA(周線)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#19D3F3', width=1.5), name='20MA(月線)'), row=1, col=1)
    
    vol_colors = [up_color if row['Close'] >= row['Open'] else down_color for idx, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], line=dict(color='#AB63FA', width=1.5), name='RSI(14)'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], line=dict(color='#19D3F3', width=1.5), name='MACD 快線'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], line=dict(color='#FFA15A', width=1.5), name='MACD 慢線(Signal)'), row=4, col=1)

    # 統一視覺風格設定
    fig.update_layout(
        title=dict(text=f'{stock_id} 互動式技術分析大師', font=dict(size=22, color="#E0E0E0")),
        height=850, 
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        xaxis_rangeslider_visible=False, 
        margin=dict(l=50, r=50, b=50, t=50), 
        hovermode='x unified',
        hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="white")),
        legend=dict(font=dict(size=14, color="white"))
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)', rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    return fig