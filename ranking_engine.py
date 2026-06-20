import pandas as pd
import yfinance as yf
import concurrent.futures
import streamlit as st
import requests

@st.cache_data(ttl=86400) # 🌟 神級快取：每天只爬一次全市場字典，秒速載入不卡頓
def get_full_market_name_dict():
    """暴力抓取官方 ISIN 碼，建立「全台股 (上市+上櫃) 2000+ 檔」純中文對照字典"""
    name_dict = {
        # 保底 50 大權值股 (以防萬一沒網路或證交所臨時維修，這些依然能正常顯示)
        "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2308": "台達電", "2382": "廣達", 
        "2881": "富邦金", "2891": "中信金", "2882": "國泰金", "2886": "兆豐金", "2884": "玉山金",
        "1216": "統一", "1301": "台塑", "1402": "遠東新", "1403": "宏洲", "2002": "中鋼", "2105": "正新",
        "2207": "和泰車", "2301": "光寶科", "2303": "聯電", "2324": "仁寶", "2345": "智邦", 
        "2357": "華碩", "2379": "瑞昱", "2395": "研華", "2408": "南亞科", "2412": "中華電", 
        "2603": "長榮", "2609": "陽明", "2615": "萬海", "2801": "彰銀", "2880": "華南金", 
        "2883": "開發金", "2885": "元大金", "2887": "台新金", "2890": "永豐金", "2892": "第一金", 
        "2912": "統一超", "3008": "大立光", "3034": "聯詠", "3045": "台灣大", "3231": "緯創", 
        "3711": "日月光投控", "4904": "遠傳", "5871": "中租-KY", "5876": "上海商銀", "5880": "合庫金", 
        "6505": "台塑化", "6669": "緯穎", "8046": "南電", "9904": "寶成",
        "0050": "元大台灣50", "0056": "元大高股息", "00878": "國泰永續高股息", "00919": "群益台灣精選高息"
    }
    
    try:
        # strMode=2 為上市，strMode=4 為上櫃
        urls = [
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"  
        ]
        for url in urls:
            res = requests.get(url, timeout=10)
            res.encoding = 'big5'
            dfs = pd.read_html(res.text)
            if dfs:
                df = dfs[0]
                df.columns = df.iloc[0]
                df = df.iloc[1:]
                if '有價證券代號及名稱' in df.columns:
                    for item in df['有價證券代號及名稱'].dropna():
                        # 分割代號與名稱 (處理全形與半形空白)
                        parts = str(item).replace('\u3000', ' ').split(' ')
                        if len(parts) >= 2:
                            code = parts[0].strip()
                            name = parts[1].strip()
                            name_dict[code] = name
    except Exception as e:
        print(f"全市場字典抓取失敗，使用保底字典: {e}")
        
    return name_dict

# 台灣 50 大權值股清單 (當您的觀察名單為空時，系統預設掃描的火力展示名單)
TW_50_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "2881.TW", "2891.TW", "2882.TW", 
    "2886.TW", "2884.TW", "1216.TW", "1301.TW", "1402.TW", "1403.TW", "2002.TW", "2105.TW",
    "2207.TW", "2301.TW", "2303.TW", "2324.TW", "2345.TW", "2357.TW", "2379.TW", "2395.TW",
    "2408.TW", "2412.TW", "2603.TW", "2609.TW", "2615.TW", "2801.TW", "2880.TW", "2883.TW",
    "2885.TW", "2887.TW", "2890.TW", "2892.TW", "2912.TW", "3008.TW", "3034.TW", "3045.TW",
    "3231.TW", "3711.TW", "4904.TW", "5871.TW", "5876.TW", "5880.TW", "6505.TW", "6669.TW",
    "8046.TW", "9904.TW"
]

def get_single_stock_factors(stock_id, full_name_dict):
    """抓取單檔股票數據，並使用全市場字典進行智能命名"""
    try:
        stock = yf.Ticker(stock_id)
        
        hist = stock.history(period="3mo")
        if hist.empty or 'Close' not in hist.columns: 
            return None
            
        clean_close = hist['Close'].dropna()
        if len(clean_close) < 20: 
            return None
            
        close_price = float(clean_close.iloc[-1])
        ma20 = float(clean_close.rolling(window=20).mean().iloc[-1])
        momentum = (close_price - ma20) / ma20  
        
        info = stock.info
        pe = info.get("trailingPE") or info.get("forwardPE")
        eps = info.get("trailingEps") or info.get("forwardEps")
        
        # 🌟 絕對防彈命名機制：對接全市場字典
        clean_id = str(stock_id).replace(".TW", "").replace(".TWO", "").strip()
        company_name = full_name_dict.get(clean_id)
        
        # 若真的遇到冷門到字典都沒有的(例如美股)，退回 Yahoo 英文名
        if not company_name:
            company_name = info.get('shortName', stock_id) 
        
        if pe is None or eps is None or pe <= 0: 
            return None
            
        return {
            "股票代號": stock_id,
            "企業名稱": company_name, 
            "收盤價": round(close_price, 2), 
            "本益比(PE)": round(pe, 2),
            "每股盈餘(EPS)": round(eps, 2),
            "動能(乖離率)": momentum
        }
    except Exception:
        return None

def run_multi_factor_ranking(target_watchlist=None):
    """執行多因子評分 (完美對接觀察名單與全市場字典)"""
    
    # 決定要掃描誰：如果有觀察名單就掃描觀察名單，沒有就掃描 50 大權值股
    if target_watchlist and isinstance(target_watchlist, list) and len(target_watchlist) > 0:
        tickers_to_scan = target_watchlist
    else:
        tickers_to_scan = TW_50_TICKERS
        
    # 🌟 載入全台股字典 (上市 + 上櫃 2000+ 檔)
    name_map = get_full_market_name_dict()
    results = []
    
    # 10 影分身極速抓取
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(get_single_stock_factors, ticker, name_map) for ticker in tickers_to_scan]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
                
    df = pd.DataFrame(results)
    if df.empty:
        return pd.DataFrame({"系統提示": ["無法取得資料，可能目標股票缺乏 PE/EPS 數據，或代號錯誤。"]})
        
    # 🌟 創辦人的超強演算法 (價值 + 品質 + 動能)
    df['Value_Score'] = (1 / df['本益比(PE)']).rank(pct=True) * 100
    df['Quality_Score'] = df['每股盈餘(EPS)'].rank(pct=True) * 100
    df['Momentum_Score'] = df['動能(乖離率)'].rank(pct=True) * 100
    df['綜合量化評分'] = (df['Value_Score'] * 0.4) + (df['Quality_Score'] * 0.3) + (df['Momentum_Score'] * 0.3)
    
    df = df.sort_values(by='綜合量化評分', ascending=False).reset_index(drop=True)
    
    df['綜合量化評分'] = df['綜合量化評分'].round(1)
    df['Value_Score'] = df['Value_Score'].round(1)
    df['Quality_Score'] = df['Quality_Score'].round(1)
    df['Momentum_Score'] = df['Momentum_Score'].round(1)
    df['動能(乖離率)'] = (df['動能(乖離率)'] * 100).round(2).astype(str) + "%"
    
    df.index = df.index + 1
    df.index.name = "排名"
    
    return df