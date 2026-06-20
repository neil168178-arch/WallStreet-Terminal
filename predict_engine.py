import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

def run_monte_carlo_simulation(df, days_to_predict=20, num_simulations=100):
    """
    執行蒙地卡羅股價路徑模擬 (Geometric Brownian Motion)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return None, None
        
    # 1. 計算歷史日報酬率
    returns = df['Close'].pct_change().dropna()
    
    # 2. 計算飄移率 (Drift) 與 波動率 (Volatility)
    mu = returns.mean()
    sigma = returns.std()
    
    last_price = df['Close'].iloc[-1]
    last_date = df.index[-1]
    
    # 3. 準備儲存所有模擬路徑的容器
    simulation_data = np.zeros((days_to_predict, num_simulations))
    
    # 4. 產生隨機漫步路徑 (核心運算)
    for x in range(num_simulations):
        prices = [last_price]
        for y in range(days_to_predict):
            # 幾何布朗運動公式 (GBM)
            shock = np.random.normal(mu, sigma)
            price = prices[-1] * (1 + shock)
            prices.append(price)
        # 捨棄第一天的初始價格，只保留未來的預測路徑
        simulation_data[:, x] = prices[1:]
        
    simulation_df = pd.DataFrame(simulation_data)
    
    # 5. 產生未來交易日的日期索引 (跳過週末)
    future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=days_to_predict)
    
    # 6. 計算機率分佈 (95% 樂觀、50% 中位、5% 悲觀)
    percentiles_df = pd.DataFrame({
        'Date': future_dates,
        '5% (悲觀支撐)': simulation_df.quantile(0.05, axis=1),
        '50% (中位預期)': simulation_df.quantile(0.50, axis=1),
        '95% (樂觀壓力)': simulation_df.quantile(0.95, axis=1)
    })
    
    return simulation_df, percentiles_df, future_dates

def plot_monte_carlo_forecast(hist_df, sim_df, percent_df, future_dates, target_stock):
    """繪製蒙地卡羅未來股價機率錐狀圖"""
    fig = go.Figure()
    
    # 取歷史最後 60 天來畫圖，讓比例比較好看
    recent_hist = hist_df.tail(60)
    
    # 1. 畫出歷史真實走勢 (白色實線)
    fig.add_trace(go.Scatter(
        x=recent_hist.index, y=recent_hist['Close'],
        mode='lines', name='過去實際走勢',
        line=dict(color='#FFFFFF', width=3)
    ))
    
    # 2. 畫出 100 條平行宇宙的模擬路徑 (低透明度細線，展現運算感)
    for i in range(sim_df.shape[1]):
        fig.add_trace(go.Scatter(
            x=future_dates, y=sim_df[i],
            mode='lines', showlegend=False,
            line=dict(color='rgba(25, 211, 243, 0.03)', width=1) # 極淡的藍色
        ))
        
    # 3. 畫出統計學上的高標、低標與中位數
    fig.add_trace(go.Scatter(
        x=percent_df['Date'], y=percent_df['95% (樂觀壓力)'],
        mode='lines', name='95% 樂觀壓力線',
        line=dict(color='#00CC96', width=2, dash='dash') # 綠色虛線
    ))
    
    fig.add_trace(go.Scatter(
        x=percent_df['Date'], y=percent_df['50% (中位預期)'],
        mode='lines', name='50% 中位預期線',
        line=dict(color='#FFA15A', width=2) # 橘色實線
    ))
    
    fig.add_trace(go.Scatter(
        x=percent_df['Date'], y=percent_df['5% (悲觀支撐)'],
        mode='lines', name='5% 悲觀支撐線',
        line=dict(color='#FF4B4B', width=2, dash='dash') # 紅色虛線
    ))
    
    # 在最後一天的歷史價格和未來預測之間加上一條垂直分割線
    last_hist_date = recent_hist.index[-1]
    fig.add_vline(x=last_hist_date, line_width=2, line_dash="dot", line_color="#E0E0E0")
    
    fig.update_layout(
        title=dict(text=f'🔮 {target_stock} 未來 20 天蒙地卡羅機率預測', font=dict(size=22, color="#E0E0E0")),
        height=550, template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'), margin=dict(l=50, r=50, b=50, t=50),
        hovermode='x unified', hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="#FFFFFF"), bordercolor="#333333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14, color="white"))
    )
    
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    
    return fig