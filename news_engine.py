import requests
from bs4 import BeautifulSoup
import pandas as pd
import google.generativeai as genai
import json
import plotly.graph_objects as go

def fetch_stock_news(stock_id):
    """抓取 Google 新聞的個股相關最新報導 (RSS)"""
    clean_id = stock_id.replace(".TW", "").replace(".TWO", "")
    url = f"https://news.google.com/rss/search?q={clean_id}+股市+股票&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        
        news_data = []
        # 🌟 升級：將限制從 [:5] 放寬到 [:15]，抓取最新 15 則新聞！
        # 因為 RSS 預設就是由新到舊排序，所以直接切片就能保證是最新的。
        for item in items[:15]: 
            news_data.append({
                "新聞標題": item.title.text,
                "發布時間": item.pubDate.text,
                "新聞連結": item.link.text
            })
            
        return pd.DataFrame(news_data)
    except Exception as e:
        print(f"抓取新聞發生錯誤: {e}")
        return pd.DataFrame()

def analyze_news_sentiment(news_df, api_key):
    """呼叫 Google Gemini API 進行新聞情緒分析 (強制 JSON 量化輸出)"""
    if news_df.empty:
        return {"error": "無法取得近期新聞，請稍後再試。"}
        
    if not api_key:
        return {"error": "⚠️ 尚未輸入 Gemini API Key！請先在左側邊欄輸入金鑰。"}
        
    try:
        news_text = "\n".join([f"- {row['新聞標題']}" for index, row in news_df.iterrows()])
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 🌟 提示詞微調：告訴 AI 它現在正在看的是「更大量」的新聞
        prompt = f"""
        你現在是一位華爾街頂尖的量化分析師。請閱讀以下關於同一檔台灣股票的最新 15 則新聞標題：
        
        {news_text}
        
        請綜合評估這批大數據，以純 JSON 格式輸出你的分析結果，不要加上任何 Markdown 標記（如 ```json），直接輸出 JSON 字串。格式必須嚴格如下：
        {{
            "score": <0 到 100 之間的整數，0代表極度看空，50代表中立，100代表極度看多>,
            "sentiment": "<極度看多/偏多/中立/偏空/極度看空>",
            "summary": "<50~100 字的精準總結，分析這些新聞對股價可能的短期影響>"
        }}
        """
        
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # 清理可能殘留的 Markdown 標記
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        # 將 AI 的回傳字串轉為 Python 字典
        result_dict = json.loads(raw_text)
        return result_dict
        
    except Exception as e:
        return {"error": f"❌ AI 分析失敗。請確認 API Key 或網路狀態。\n詳細錯誤：{e}"}

def plot_sentiment_gauge(score, sentiment_text):
    """繪製高質感 AI 情緒儀表板"""
    # 決定指針顏色
    if score >= 80: bar_color = "#19D3F3" # 極度看多 (藍)
    elif score >= 60: bar_color = "#00CC96" # 偏多 (綠)
    elif score >= 40: bar_color = "#E0E0E0" # 中立 (灰)
    elif score >= 20: bar_color = "#FFA15A" # 偏空 (橘)
    else: bar_color = "#FF4B4B" # 極度看空 (紅)

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        title = {'text': f"🤖 AI 投資情緒: {sentiment_text}", 'font': {'size': 20, 'color': '#E0E0E0'}},
        number = {'font': {'color': bar_color, 'size': 50}},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.5)"},
            'bar': {'color': bar_color, 'thickness': 0.25},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [0, 20], 'color': "rgba(255, 75, 75, 0.15)"},
                {'range': [20, 40], 'color': "rgba(255, 161, 90, 0.15)"},
                {'range': [40, 60], 'color': "rgba(224, 224, 224, 0.15)"},
                {'range': [60, 80], 'color': "rgba(0, 204, 150, 0.15)"},
                {'range': [80, 100], 'color': "rgba(25, 211, 243, 0.15)"}
            ]
        }
    ))
    
    fig.update_layout(
        height=350, margin=dict(l=30, r=30, t=50, b=30),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0')
    )
    return fig