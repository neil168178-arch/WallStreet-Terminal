import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import plotly.graph_objects as go
from strategy_engine import add_indicators

def run_ai_prediction(df):
    """
    使用隨機森林 (Random Forest) 進行明日漲跌機率預測
    """
    if len(df) < 50:
        return None, None
        
    # 1. 準備特徵值 (Features)：使用我們寫好的技術指標
    data = add_indicators(df.copy())
    data['Return'] = data['Close'].pct_change() # 每日報酬率
    
    # 2. 準備目標值 (Target)：如果「明天的收盤價」大於「今天的收盤價」，標記為 1 (上漲)，否則為 0 (下跌)
    data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
    
    # 移除空值 (最後一天沒有「明天」的資料，所以會被 drop 掉，剛好用來做最終預測)
    data = data.dropna()
    
    # 我們讓 AI 學習這 5 個特徵
    features = ['MA5', 'MA20', 'RSI_14', 'MACD_12_26_9', 'Return']
    
    if len(data) < 30:
        return None, None
        
    # 取出訓練資料 (不包含最後一天)
    X_train = data[features][:-1]
    y_train = data['Target'][:-1]
    
    # 3. 建立並訓練 AI 模型 (100 棵決策樹的隨機森林)
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    # 4. 預測「最新一天」的明日上漲機率
    latest_data = data[features].iloc[-1:]
    prob_up = model.predict_proba(latest_data)[0][1] * 100 # 取出上漲(1)的機率並轉為百分比
    
    # 5. 分析哪些技術指標最重要 (為了配合 Plotly 橫向長條圖，這裡改成 ascending=True)
    importance = pd.Series(model.feature_importances_, index=features).sort_values(ascending=True)
    
    return prob_up, importance

def plot_ml_prediction(prob_up, importance):
    """繪製機器學習預測儀表板與特徵權重圖 (已拆分為兩張獨立圖表以支援手機 RWD)"""
    
    # 決定顏色 (大於 50% 偏多用綠色，小於 50% 偏空用紅色)
    bar_color = "#00CC96" if prob_up >= 50 else "#FF4B4B"
    
    # ==========================================
    # 📊 第一張圖：AI 勝率儀表板 (fig1)
    # ==========================================
    fig1 = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = prob_up,
        title = {'text': "明日上漲機率", 'font': {'size': 20, 'color': '#E0E0E0'}},
        number = {'suffix': "%", 'font': {'color': bar_color, 'size': 40}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.5)"},
            'bar': {'color': bar_color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [0, 50], 'color': "rgba(255, 75, 75, 0.15)"},
                {'range': [50, 100], 'color': "rgba(0, 204, 150, 0.15)"}
            ]
        }
    ))
    
    fig1.update_layout(
        title=dict(text='🤖 AI 預測結果', font=dict(size=22, color="#E0E0E0")),
        height=350, template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        margin=dict(l=30, r=30, t=60, b=30)
    )
    
    # ==========================================
    # 📊 第二張圖：特徵權重長條圖 (fig2)
    # ==========================================
    fig2 = go.Figure(go.Bar(
        x=importance.values,
        y=importance.index,
        orientation='h',
        marker_color='#19D3F3',
        name="決策權重"
    ))
    
    fig2.update_layout(
        title=dict(text='🧠 AI 決策關鍵指標權重', font=dict(size=18, color="#E0E0E0")),
        height=350, template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        showlegend=False,
        margin=dict(l=30, r=30, t=60, b=30),
        xaxis=dict(title="影響力佔比", gridcolor='rgba(255, 255, 255, 0.1)'),
        yaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)')
    )
    
    # 🌟 終極大決招：不再只回傳一個，而是把兩張圖一起打包傳出去！
    return fig1, fig2