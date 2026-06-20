import pandas as pd

def calculate_risk_metrics(backtest_results, total_capital):
    """
    計算凱利公式最佳資金比例與最大回撤 (Max Drawdown)
    """
    # 取出策略有「進場持有」的日子
    invested_days = backtest_results[backtest_results['Position'] == 1]
    
    if len(invested_days) == 0:
        return 0, 0, 0
        
    # 計算勝率與賠率
    wins = invested_days[invested_days['Strategy_Return'] > 0]
    losses = invested_days[invested_days['Strategy_Return'] < 0]
    
    win_rate = len(wins) / len(invested_days) if len(invested_days) > 0 else 0
    avg_win = wins['Strategy_Return'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['Strategy_Return'].mean()) if len(losses) > 0 else 0
    
    win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
    
    # 1. 凱利公式計算 (Kelly Criterion: f* = W - [(1 - W) / R])
    if win_loss_ratio > 0:
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)
    else:
        kelly_pct = 0
        
    # 實戰中通常使用「半凱利 (Half-Kelly)」以降低風險
    safe_kelly = max(0, kelly_pct / 2)
    suggested_allocation = total_capital * safe_kelly
    
    # 2. 計算最大回撤 (Max Drawdown)：歷史最高點摔下來的最深跌幅
    cumulative = backtest_results['策略累計報酬']
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_dd = drawdown.min() * 100
    
    return safe_kelly * 100, suggested_allocation, max_dd