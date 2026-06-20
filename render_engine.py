import streamlit as st
import pandas as pd

# ==========================================
# 🌐 全域英文轉中文字典
# ==========================================
GLOBAL_TW_DICT = {
    'Date': '日期', 'Close': '收盤價', 'Open': '開盤價', 'High': '最高價', 'Low': '最低價', 'Volume': '成交量',
    'Market Cap': '總市值', 'PE Ratio': '本益比 (PE)', 'Forward PE': '預估本益比', 'EPS': '每股盈餘 (EPS)',
    'Dividend Yield': '殖利率', 'ROE': '股東權益報酬率 (ROE)', 'ROA': '資產報酬率 (ROA)',
    'Revenue Growth': '營收成長率', 'Profit Margin': '淨利率', 'Debt to Equity': '負債比',
    'Current Price': '目前股價', 'Target Price': '目標價', 'Recommendation': '機構評級',
    'Short_MA': '短期均線', 'Long_MA': '長期均線', 'ROI': '總報酬率(%)', 'Equity': '總資金',
    'Value_Score': '價值分數 (便宜度)', 
    'Quality_Score': '品質分數 (獲利力)', 
    'Momentum_Score': '動能分數 (強勢度)',
    'Type': '交易動作', 'Price': '成交價格', 'Shares': '交易股數', 'PnL': '單筆損益'
}

def translate_df(df):
    """在將 DataFrame 顯示到網頁前，將英文欄位翻譯成中文"""
    if df is None or df.empty:
        return df
    translated = df.copy()
    translated.rename(columns=GLOBAL_TW_DICT, inplace=True)
    return translated

def render_dataframe(df, hide_index=True, link_col=None):
    """將 DataFrame 英文欄位翻譯成中文，並透過 Pandas Styler 強制置中對齊與智能小數點格式化"""
    if df is None or df.empty:
        st.dataframe(df, use_container_width=True, hide_index=hide_index)
        return
        
    translated = df.copy()
    translated.rename(columns=GLOBAL_TW_DICT, inplace=True)
    
    # 🌟 智能小數點與千分位格式化
    format_dict = {}
    for col in translated.columns:
        if pd.api.types.is_numeric_dtype(translated[col]):
            # 大數字與張數：整數 + 千分位逗號
            if col in ['成交量', '總市值', '總資金', '總投資成本', '總投資成本(元)', '目前總市值', '未實現損益', '持股數量(股)', '交易股數']:
                format_dict[col] = "{:,.0f}"
            # 排名：純整數
            elif '排名' in col:
                format_dict[col] = "{:.0f}"
            # 股價、分數、比例：保留兩位小數
            else:
                format_dict[col] = "{:.2f}"
                
    try:
        styled_df = translated.style.format(format_dict, na_rep="-") \
                                    .set_properties(**{'text-align': 'center'}) \
                                    .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
        
        if link_col:
            st.dataframe(styled_df, use_container_width=True, hide_index=hide_index, column_config={link_col: st.column_config.LinkColumn("點此閱讀原文")})
        else:
            st.dataframe(styled_df, use_container_width=True, hide_index=hide_index)
    except Exception:
        # 防呆：若 Styler 出錯，退回一般顯示
        st.dataframe(translated, use_container_width=True, hide_index=hide_index)

# ==========================================
# 🎨 專屬 UI 補丁：修正白色按鍵與下拉選單
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
    /* 修復 Expander (白話文教學/下拉清單) 的白底問題，完美融入 Midnight Dark Theme */
    [data-testid="stExpander"] details {
        background-color: transparent !important;
        border: none !important;
    }
    [data-testid="stExpander"] details summary {
        background-color: #2A2D3E !important;
        border: 1px solid #4A4D5E !important;
        border-radius: 8px !important;
        padding: 10px 15px !important;
    }
    [data-testid="stExpander"] details summary p {
        color: #19D3F3 !important; 
        font-weight: bold !important;
        font-size: 18px !important;
    }
    [data-testid="stExpander"] details summary:hover {
        background-color: #FF4B4B !important;
        border-color: #FF4B4B !important;
    }
    [data-testid="stExpander"] details summary:hover p {
        color: #FFFFFF !important;
    }
    [data-testid="stExpander"] details summary svg {
        fill: #19D3F3 !important;
    }
    [data-testid="stExpander"] details summary:hover svg {
        fill: #FFFFFF !important;
    }
    [data-testid="stExpander"] details div[data-testid="stExpanderDetails"] {
        background-color: #1E1E2E !important;
        border: 1px solid #4A4D5E !important;
        border-top: none !important;
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
        padding: 15px;
    }
    </style>
    """, unsafe_allow_html=True)