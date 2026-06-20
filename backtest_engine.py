import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import numpy as np

def run_advanced_backtest(df, initial_capital, fee_discount, is_etf=False, 
                          strategy_type='ma_cross', # 🌟 核心升級：加入策略排檔桿
                          use_trend_filter=True, stop_loss_pct=0.05, take_profit_pct=0.10,
                          short_window=5, long_window=20,
                          use_atr=False, atr_sl_mult=2.0, atr_tp_mult=4.0, risk_pct=2.0,
                          allow_short=False, use_chips_filter=False, slippage_pct=0.002):
    """單檔股票回測引擎 (含滑價模擬與 5 大策略模組)"""
    if df is None or df.empty: return None, None, None

    df = df.copy()
    
    # 防呆：確保技術指標已經載入 (若沒有則呼叫 strategy_engine)
    if 'RSI_14' not in df.columns:
        from strategy_engine import add_indicators
        df = add_indicators(df)

    # 動態計算均線 (為了讓暴力破解器可以變更參數)
    df['SMA_short'] = df['Close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['Close'].rolling(window=long_window).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()

    prev_close = df['Close'].shift(1)
    df['TR'] = pd.concat([df['High'] - df['Low'], (df['High'] - prev_close).abs(), (df['Low'] - prev_close).abs()], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    capital = initial_capital
    position = 0  
    entry_price = 0 
    dynamic_sl = dynamic_tp = 0
    trade_history = []
    equity_curve = []
    tax_rate = 0.001 if is_etf else 0.003

    # ==========================================
    # 🌟 策略大腦切換區：定義進出場訊號
    # ==========================================
    if strategy_type == 'ma_cross':
        golden_cross = (df['SMA_short'] > df['SMA_long']) & (df['SMA_short'].shift(1) <= df['SMA_long'].shift(1))
        dead_cross = (df['SMA_short'] < df['SMA_long']) & (df['SMA_short'].shift(1) >= df['SMA_long'].shift(1))
        long_sig, short_sig = golden_cross, dead_cross
        exit_long, exit_short = dead_cross, golden_cross
        
    elif strategy_type == 'macd_cross':
        macd_up = (df['MACDh_12_26_9'] > 0) & (df['MACDh_12_26_9'].shift(1) <= 0)
        macd_down = (df['MACDh_12_26_9'] < 0) & (df['MACDh_12_26_9'].shift(1) >= 0)
        long_sig = macd_up & (df['Close'] > df['SMA_long'])
        short_sig = macd_down & (df['Close'] < df['SMA_long'])
        exit_long, exit_short = macd_down, macd_up
        
    elif strategy_type == 'rsi_reversion':
        long_sig = (df['RSI_14'] < 30)
        short_sig = (df['RSI_14'] > 70)
        exit_long, exit_short = (df['RSI_14'] > 70), (df['RSI_14'] < 30)
        
    elif strategy_type == 'bb_breakout':
        long_sig = (df['Close'] > df['BBU_20_2.0'])
        short_sig = (df['Close'] < df['BBL_20_2.0'])
        exit_long, exit_short = (df['Close'] < df['SMA_long']), (df['Close'] > df['SMA_long'])
        
    elif strategy_type == 'combined':
        long_sig = (df['MACDh_12_26_9'] > 0) & (df['RSI_14'] > 50) & (df['Close'] > df['MA60'])
        short_sig = (df['MACDh_12_26_9'] < 0) & (df['RSI_14'] < 50) & (df['Close'] < df['MA60'])
        exit_long, exit_short = (df['MACDh_12_26_9'] < 0), (df['MACDh_12_26_9'] > 0)
        
    else: # Default fallback
        long_sig = short_sig = exit_long = exit_short = pd.Series(False, index=df.index)

    # 疊加您的核心風控：趨勢濾網與籌碼濾網
    long_cond = long_sig & (df['Close'] > df['MA60']) if use_trend_filter else long_sig
    short_cond = short_sig & (df['Close'] < df['MA60']) if use_trend_filter else short_sig

    if use_chips_filter and 'Chips_3D_Sum' in df.columns:
        long_cond = long_cond & (df['Chips_3D_Sum'] > 0)
        short_cond = short_cond & (df['Chips_3D_Sum'] < 0)

    # ==========================================
    # 保留您完美的事件驅動引擎 (ATR / 滑價)
    # ==========================================
    for date, row in df.iterrows():
        price = row['Close']
        atr_val = row['ATR']

        if position == 0:
            if long_cond[date]: 
                real_price = price * (1 + slippage_pct) # 🌟 滑價：買得更貴
                cost_rate = 1 + (0.001425 * fee_discount)
                
                if use_atr and pd.notna(atr_val):
                    sl_dist = atr_val * atr_sl_mult
                    risk_shares = int((capital * (risk_pct / 100.0)) / sl_dist) if sl_dist > 0 else 0
                    shares = min(risk_shares, int(capital / (real_price * cost_rate)))
                    dynamic_sl, dynamic_tp = real_price - sl_dist, real_price + (atr_val * atr_tp_mult)
                else:
                    shares = int(capital / (real_price * cost_rate))
                    dynamic_sl, dynamic_tp = real_price * (1 - stop_loss_pct), real_price * (1 + take_profit_pct)
                
                if shares > 0:
                    capital -= shares * real_price * cost_rate
                    position = shares
                    entry_price = real_price
                    trade_history.append({'動作': '🔴 買進(含滑價)', '日期': date, '成交價': round(real_price,2), '股數': position, '獲利': 0})

            elif allow_short and short_cond[date]:
                real_price = price * (1 - slippage_pct) # 🌟 滑價：空得更便宜
                cost_rate = 1 - (0.001425 * fee_discount) 
                
                if use_atr and pd.notna(atr_val):
                    sl_dist = atr_val * atr_sl_mult
                    risk_shares = int((capital * (risk_pct / 100.0)) / sl_dist) if sl_dist > 0 else 0
                    shares = min(risk_shares, int(capital / real_price))
                    dynamic_sl, dynamic_tp = real_price + sl_dist, real_price - (atr_val * atr_tp_mult)
                else:
                    shares = int(capital / real_price)
                    dynamic_sl, dynamic_tp = real_price * (1 + stop_loss_pct), real_price * (1 - take_profit_pct)

                if shares > 0:
                    capital += shares * real_price * cost_rate 
                    position = -shares 
                    entry_price = real_price
                    trade_history.append({'動作': '🐻 做空(含滑價)', '日期': date, '成交價': round(real_price,2), '股數': abs(position), '獲利': 0})

        elif position > 0:
            exit_reason = ""
            if price <= dynamic_sl: exit_reason = "🛑 多單停損"
            elif price >= dynamic_tp: exit_reason = "🎉 多單停利"
            elif exit_long[date]: exit_reason = "🟢 多單平倉 (訊號反轉)"

            if exit_reason:
                real_price = price * (1 - slippage_pct) # 🌟 滑價：賣得更便宜
                sell_rate = 1 - (0.001425 * fee_discount) - tax_rate
                revenue = position * real_price * sell_rate
                capital += revenue
                profit = revenue - (position * entry_price * (1 + 0.001425 * fee_discount))
                trade_history.append({'動作': exit_reason, '日期': date, '成交價': round(real_price,2), '股數': position, '獲利': int(profit)})
                position = 0

        elif position < 0:
            exit_reason = ""
            if price >= dynamic_sl: exit_reason = "🛑 空單停損"
            elif price <= dynamic_tp: exit_reason = "🎉 空單停利"
            elif exit_short[date]: exit_reason = "🟢 空單回補 (訊號反轉)"

            if exit_reason:
                real_price = price * (1 + slippage_pct) # 🌟 滑價：回補買得更貴
                buy_rate = 1 + (0.001425 * fee_discount)
                cost = abs(position) * real_price * buy_rate
                capital -= cost 
                profit = (abs(position) * entry_price * (1 - 0.001425 * fee_discount - tax_rate)) - cost
                trade_history.append({'動作': exit_reason, '日期': date, '成交價': round(real_price,2), '股數': abs(position), '獲利': int(profit)})
                position = 0

        current_equity = capital + (position * price)
        equity_curve.append({'Date': date, 'Equity': current_equity})

    return _compile_metrics(equity_curve, trade_history, initial_capital)


# =====================================================================
# 🌟 全市場投資組合回測 (Portfolio Backtest)
# =====================================================================
def run_portfolio_backtest(data_dict, initial_capital, fee_discount, 
                           strategy_type='ma_cross', # 🌟 核心升級：支援策略切換
                           use_filter=True, sl_pct=0.05, tp_pct=0.10, short_window=5, long_window=20, 
                           use_atr=True, atr_sl_mult=2.0, atr_tp_mult=4.0, risk_pct=2.0, 
                           allow_short=False, slippage_pct=0.002, max_alloc_per_ticker=0.2):
    records = []
    
    for tk, df in data_dict.items():
        if df.empty: continue
        df = df.copy()
        if 'RSI_14' not in df.columns:
            from strategy_engine import add_indicators
            df = add_indicators(df)

        df['SMA_short'] = df['Close'].rolling(window=short_window).mean()
        df['SMA_long'] = df['Close'].rolling(window=long_window).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['ATR'] = (pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift(1)).abs(), (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1)).rolling(14).mean()
        
        # 依照選擇的策略動態產生訊號
        if strategy_type == 'ma_cross':
            long_sig = (df['SMA_short'] > df['SMA_long']) & (df['SMA_short'].shift(1) <= df['SMA_long'].shift(1))
            short_sig = (df['SMA_short'] < df['SMA_long']) & (df['SMA_short'].shift(1) >= df['SMA_long'].shift(1))
            exit_long, exit_short = short_sig, long_sig
        elif strategy_type == 'macd_cross':
            long_sig = (df['MACDh_12_26_9'] > 0) & (df['MACDh_12_26_9'].shift(1) <= 0) & (df['Close'] > df['SMA_long'])
            short_sig = (df['MACDh_12_26_9'] < 0) & (df['MACDh_12_26_9'].shift(1) >= 0) & (df['Close'] < df['SMA_long'])
            exit_long, exit_short = (df['MACDh_12_26_9'] < 0), (df['MACDh_12_26_9'] > 0)
        elif strategy_type == 'rsi_reversion':
            long_sig, short_sig = (df['RSI_14'] < 30), (df['RSI_14'] > 70)
            exit_long, exit_short = short_sig, long_sig
        elif strategy_type == 'bb_breakout':
            long_sig, short_sig = (df['Close'] > df['BBU_20_2.0']), (df['Close'] < df['BBL_20_2.0'])
            exit_long, exit_short = (df['Close'] < df['SMA_long']), (df['Close'] > df['SMA_long'])
        else: # combined
            long_sig = (df['MACDh_12_26_9'] > 0) & (df['RSI_14'] > 50) & (df['Close'] > df['MA60'])
            short_sig = (df['MACDh_12_26_9'] < 0) & (df['RSI_14'] < 50) & (df['Close'] < df['MA60'])
            exit_long, exit_short = (df['MACDh_12_26_9'] < 0), (df['MACDh_12_26_9'] > 0)

        df['Long_Sig'] = long_sig & (df['Close'] > df['MA60']) if use_filter else long_sig
        df['Short_Sig'] = short_sig & (df['Close'] < df['MA60']) if use_filter else short_sig
        df['Exit_Long'], df['Exit_Short'] = exit_long, exit_short
        
        for date, row in df.iterrows():
            records.append({
                'Date': date, 'Ticker': tk, 'Close': row['Close'],
                'Long_Sig': row['Long_Sig'], 'Short_Sig': row['Short_Sig'],
                'Exit_Long': row['Exit_Long'], 'Exit_Short': row['Exit_Short'], 'ATR': row['ATR']
            })
            
    if not records: return None, None, None
    master_df = pd.DataFrame(records).sort_values('Date')
    
    capital = initial_capital
    positions = {} 
    trade_history, equity_history = [], []
    tax_rate = 0.003
    
    for date, group in master_df.groupby('Date'):
        # A. 優先出場
        for idx, row in group.iterrows():
            tk, price = row['Ticker'], row['Close']
            if tk in positions:
                pos = positions[tk]
                exit_reason = ""
                
                if pos['type'] == 'long':
                    if price <= pos['sl']: exit_reason = "🛑 多單停損"
                    elif price >= pos['tp']: exit_reason = "🎉 多單停利"
                    elif row['Exit_Long']: exit_reason = "🟢 平倉(訊號反轉)"
                    
                    if exit_reason:
                        real_price = price * (1 - slippage_pct)
                        revenue = pos['shares'] * real_price * (1 - 0.001425 * fee_discount - tax_rate)
                        capital += revenue
                        profit = revenue - pos['cost']
                        trade_history.append({'日期': date, '代號': tk, '動作': exit_reason, '成交價': round(real_price,2), '獲利': int(profit)})
                        del positions[tk]
                        
                elif pos['type'] == 'short':
                    if price >= pos['sl']: exit_reason = "🛑 空單停損"
                    elif price <= pos['tp']: exit_reason = "🎉 空單停利"
                    elif row['Exit_Short']: exit_reason = "🟢 回補(訊號反轉)"
                    
                    if exit_reason:
                        real_price = price * (1 + slippage_pct)
                        cost = pos['shares'] * real_price * (1 + 0.001425 * fee_discount)
                        capital -= cost
                        profit = pos['revenue'] - cost
                        trade_history.append({'日期': date, '代號': tk, '動作': exit_reason, '成交價': round(real_price,2), '獲利': int(profit)})
                        del positions[tk]

        # B. 處理進場
        for idx, row in group.iterrows():
            tk, price, atr = row['Ticker'], row['Close'], row['ATR']
            if tk not in positions:
                max_invest = initial_capital * max_alloc_per_ticker
                available = min(capital, max_invest)
                
                if available > 0:
                    if row['Long_Sig']:
                        real_price = price * (1 + slippage_pct)
                        c_rate = 1 + (0.001425 * fee_discount)
                        if use_atr and pd.notna(atr) and atr > 0:
                            sl_dist = atr * atr_sl_mult
                            risk_shares = int((initial_capital * (risk_pct/100)) / sl_dist) if sl_dist>0 else 0
                            shares = min(risk_shares, int(available / (real_price * c_rate)))
                            sl, tp = real_price - sl_dist, real_price + (atr * atr_tp_mult)
                        else:
                            shares = int(available / (real_price * c_rate))
                            sl, tp = real_price * (1 - sl_pct), real_price * (1 + tp_pct)
                            
                        if shares > 0:
                            cost = shares * real_price * c_rate
                            capital -= cost
                            positions[tk] = {'type': 'long', 'shares': shares, 'entry_price': real_price, 'sl': sl, 'tp': tp, 'cost': cost}
                            trade_history.append({'日期': date, '代號': tk, '動作': '🔴 做多', '成交價': round(real_price,2), '獲利': 0})
                            
                    elif allow_short and row['Short_Sig']:
                        real_price = price * (1 - slippage_pct)
                        if use_atr and pd.notna(atr) and atr > 0:
                            sl_dist = atr * atr_sl_mult
                            shares = min(int((initial_capital * (risk_pct/100)) / sl_dist), int(available / real_price)) if sl_dist>0 else 0
                            sl, tp = real_price + sl_dist, real_price - (atr * atr_tp_mult)
                        else:
                            shares = int(available / real_price)
                            sl, tp = real_price * (1 + sl_pct), real_price * (1 - tp_pct)
                            
                        if shares > 0:
                            revenue = shares * real_price * (1 - 0.001425 * fee_discount - tax_rate)
                            capital += revenue 
                            positions[tk] = {'type': 'short', 'shares': shares, 'entry_price': real_price, 'sl': sl, 'tp': tp, 'revenue': revenue}
                            trade_history.append({'日期': date, '代號': tk, '動作': '🐻 做空', '成交價': round(real_price,2), '獲利': 0})

        # C. 記錄市值
        pos_value = 0
        for tk, pos in positions.items():
            curr_price = group[group['Ticker'] == tk]['Close'].values[0]
            if pos['type'] == 'long': pos_value += pos['shares'] * curr_price
            elif pos['type'] == 'short': pos_value -= pos['shares'] * curr_price 
                
        equity_history.append({'Date': date, 'Equity': capital + pos_value})

    return _compile_metrics(equity_history, trade_history, initial_capital)

# =====================================================================
# 共用 Helper 函數 (完全保留您的寫法)
# =====================================================================
def _compile_metrics(equity_curve, trade_history, initial_capital):
    eq_df = pd.DataFrame(equity_curve)
    tr_df = pd.DataFrame(trade_history)
    win_rate = total_profit = total_trades = max_dd = 0

    if not tr_df.empty and '獲利' in tr_df.columns:
        exits = tr_df[tr_df['獲利'] != 0] 
        win_rate = (exits['獲利'] > 0).mean() * 100 if not exits.empty else 0
        total_profit = exits['獲利'].sum() if not exits.empty else 0
        total_trades = len(exits)

    final_equity = eq_df['Equity'].iloc[-1] if not eq_df.empty else initial_capital
    roi = ((final_equity - initial_capital) / initial_capital) * 100
    
    if not eq_df.empty:
        eq_df['HighValue'] = eq_df['Equity'].cummax()
        eq_df['Drawdown'] = (eq_df['Equity'] - eq_df['HighValue']) / eq_df['HighValue']
        max_dd = eq_df['Drawdown'].min() * 100

    metrics = {'Final Equity': final_equity, 'ROI (%)': roi, 'Win Rate (%)': win_rate, 'Max Drawdown (%)': max_dd, 'Total Trades': total_trades, 'Total Profit': total_profit}
    return eq_df, tr_df, metrics

def run_out_of_sample_optimization(df, initial_capital, fee_discount, is_etf, strategy_type, use_filter, sl, tp, use_atr, a_sl, a_tp, r_pct, allow_short, use_chips, slippage_pct):
    split_idx = int(len(df) * 0.7)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    best_roi, best_params = -999, (5, 20)
    
    for short_ma in range(3, 11):
        for long_ma in range(15, 26):
            if short_ma >= long_ma: continue
            _, _, metrics = run_advanced_backtest(train_df, initial_capital, fee_discount, is_etf, strategy_type, use_filter, sl, tp, short_ma, long_ma, use_atr, a_sl, a_tp, r_pct, allow_short, use_chips, slippage_pct)
            if metrics and metrics['ROI (%)'] > best_roi:
                best_roi, best_params = metrics['ROI (%)'], (short_ma, long_ma)

    oos_eq, oos_tr, oos_m = run_advanced_backtest(test_df, initial_capital, fee_discount, is_etf, strategy_type, use_filter, sl, tp, best_params[0], best_params[1], use_atr, a_sl, a_tp, r_pct, allow_short, use_chips, slippage_pct)
    return best_params, best_roi, oos_eq, oos_tr, oos_m

def run_parameter_grid_search(df, initial_capital, fee_discount, is_etf, strategy_type, use_filter, sl, tp, use_atr, atr_sl_mult, atr_tp_mult, risk_pct, allow_short, slippage_pct):
    results = []
    for short_ma in range(3, 13):
        for long_ma in range(15, 31):
            if short_ma >= long_ma: continue
            _, _, metrics = run_advanced_backtest(df, initial_capital, fee_discount, is_etf, strategy_type, use_filter, sl, tp, short_ma, long_ma, use_atr, atr_sl_mult, atr_tp_mult, risk_pct, allow_short, False, slippage_pct)
            if metrics: results.append({'Short_MA': short_ma, 'Long_MA': long_ma, 'ROI': metrics['ROI (%)']})
    results_df = pd.DataFrame(results)
    return results_df.pivot(index='Short_MA', columns='Long_MA', values='ROI'), results_df.loc[results_df['ROI'].idxmax()]

# =====================================================================
# 🎨 嚴格遵守您 visual_engine 設計語彙的圖表渲染器
# =====================================================================
def plot_equity_curve(equity_df, title='📈 策略資金累積曲線'):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity_df['Date'], y=equity_df['Equity'], mode='lines', name='總資金 (台幣)', line=dict(color='#19D3F3', width=2), fill='tozeroy', fillcolor='rgba(25, 211, 243, 0.1)'))
    fig.update_layout(
        title=dict(text=title, font=dict(size=22, color="#E0E0E0")), 
        height=450, 
        template='plotly_dark', 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        font=dict(color='#E0E0E0'), 
        margin=dict(l=50, r=50, b=50, t=50), 
        hovermode='x unified',
        hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="white")),
        legend=dict(font=dict(size=14, color="white"))
    )
    fig.update_xaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    return fig

def plot_optimization_heatmap(pivot_df):
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values, x=pivot_df.columns, y=pivot_df.index, 
        colorscale=[[0.0, '#FF4B4B'], [0.5, '#1E1E1E'], [1.0, '#00CC96']], 
        hoverongaps = False
    ))
    fig.update_layout(
        title=dict(text='🔥 參數暴力破解熱力圖', font=dict(size=22, color="#E0E0E0")), 
        height=500, 
        template='plotly_dark', 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        font=dict(color='#E0E0E0'),
        margin=dict(l=50, r=50, b=50, t=50),
        hoverlabel=dict(bgcolor="#1E1E1E", font=dict(size=15, color="white"))
    )
    fig.update_xaxes(title="長均線 (Long MA)", tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    fig.update_yaxes(title="短均線 (Short MA)", tickfont=dict(color='#E0E0E0'), gridcolor='rgba(255, 255, 255, 0.1)')
    return fig