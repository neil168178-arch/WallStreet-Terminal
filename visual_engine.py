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
        
        /* ======================================================== */
        /* 🚀 終極修復：擊破 Streamlit React Portal 浮動選單限制 */
        /* ======================================================== */
        /* 1. 下拉選單「框框」本體 */
        div[data-baseweb="select"] > div {
            background-color: #262730 !important; 
            border-color: #4A4A4A !important;
        }
        div[data-baseweb="select"] * {
            color: #FFFFFF !important;
        }
        
        /* 2. 穿透覆蓋：真正展開的那塊「浮動幽靈選單」 (全局鎖定) */
        div[data-baseweb="popover"] * {
            color: #FFFFFF !important;
        }
        ul[data-baseweb="menu"] {
            background-color: #262730 !important;
        }
        li[role="option"] {
            background-color: #262730 !important;
            color: #FFFFFF !important;
        }
        li[role="option"] * {
            color: #FFFFFF !important;
        }
        /* 滑鼠移過去的時候變成紅色，質感大提升 */
        li[role="option"]:hover, li[aria-selected="true"] {
            background-color: #FF4B4B !important;
            color: #FFFFFF !important;
        }
        
        /* 其他輸入框 */
        .stApp input, .stApp div[data-baseweb="base-input"] { 
            background-color: #262730 !important; color: #FFFFFF !important; font-size: 16px !important; 
            border-color: #4A4A4A !important;
        }
        /* ======================================================== */

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
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFA15A', width=1.5), name='5MA'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#19D3F3', width=1.5), name='20MA'), row=1, col=1)
    
    vol_colors = [up_color if row['Close'] >= row['Open'] else down_color for idx, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], line=dict(color='#AB63FA', width=1.5), name='RSI(14)'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], line=dict(color='#19D3F3', width=1.5), name='MACD 快線'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], line=dict(color='#FFA15A', width=1.5), name='MACD 慢線'), row=4, col=1)

    # 統一視覺風格設定
    fig.update_layout(
        # 🌟 修正 1：縮小標題字體並鎖定位置
        title=dict(
            text=f'{stock_id} 互動式技術分析大師', 
            font=dict(size=18, color="#E0E0E0"),
            y=0.97, 
            x=0.02
        ),
        height=850, 
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        xaxis_rangeslider_visible=False, 
        # 🌟 修正 2：挑高天花板 (t=100) 並減少左右邊距 (l=15, r=15)，極大化畫布寬度！
        margin=dict(l=15, r=15, b=50, t=100), 
        hovermode='x unified',
        hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="white")),
        
        # 🌟 修正 3：神級排版！將圖例變成「水平排列 (orientation='h')」，並推到圖表最上方
        legend=dict(
            orientation="h",      # 水平排列
            yanchor="bottom",     # 從底部對齊
            y=1.02,               # 推到圖表上方
            xanchor="right",      # 靠右對齊
            x=1,
            font=dict(size=12, color="white")
        )
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)', rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    return fig