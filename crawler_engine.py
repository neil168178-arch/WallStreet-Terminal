import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests  # 🌟 改用內建的網頁請求模組

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    """
    🌟 全新升級：從「台灣政府開放資料」直接獲取全台股中文名稱字典
    速度更快、無需第三方套件，自動分辨 上市(.TW) 與 上櫃(.TWO)
    """
    name_dict = {}
    try:
        # 1. 抓取上市股票 (.TW)
        twse_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        res_twse = requests.get(twse_url, timeout=10)
        if res_twse.status_code == 200:
            for item in res_twse.json():
                stock_id = str(item.get("公司代號", "")).strip()
                stock_name = str(item.get("公司名稱", "")).strip()
                if len(stock_id) >= 4 and stock_id.isdigit():
                    full_ticker = f"{stock_id}.TW"
                    name_dict[full_ticker] = stock_name
                    name_dict[stock_name] = full_ticker
                    name_dict[stock_id] = full_ticker

        # 2. 抓取上櫃股票 (.TWO)
        tpex_url = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
        res_tpex = requests.get(tpex_url, timeout=10)
        if res_tpex.status_code == 200:
            for item in res_tpex.json():
                stock_id = str(item.get("公司代號", "")).strip()
                stock_name = str(item.get("公司名稱", "")).strip()
                if len(stock_id) >= 4 and stock_id.isdigit():
                    full_ticker = f"{stock_id}.TWO"
                    name_dict[full_ticker] = stock_name
                    name_dict[stock_name] = full_ticker
                    name_dict[stock_id] = full_ticker

    except Exception as e:
        print(f"官方 OpenData 股票名稱獲取失敗: {e}")

    # 3. 疊加基本的安全名單 (Fallback 防呆機制)
    fallback = _get_fallback_stock_map()
    for k, v in fallback.items():
        if k not in name_dict:
            name_dict[k] = v
            
    return name_dict

def _get_fallback_stock_map():
    # 建立基礎的雙向字典 (當政府 API 維修時的備用電源)
    base_map = {
        "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2603.TW": "長榮",
        "2498.TW": "宏達電", "2303.TW": "聯電", "3231.TW": "緯創", "2376.TW": "技嘉",
        "3675.TWO": "德微", "3293.TWO": "鈊象", "3105.TWO": "穩懋", "8069.TWO": "元太"
    }
    res = {}
    for full_ticker, cn_name in base_map.items():
        res[full_ticker] = cn_name
        res[cn_name] = full_ticker
        res[full_ticker.split('.')[0]] = full_ticker # 把純數字也對應到含後綴的正確代號
    return res

def resolve_ticker(input_str):
    """強化的股票代號翻譯引擎"""
    if not input_str:
        return None
        
    input_str = input_str.strip()
    
    # 1. 已經是標準格式 (例如 2498.TW 或 3675.TWO)
    if re.match(r'^\d{4,6}\.TW[O]?$', input_str.upper()):
        return input_str.upper()
        
    # 呼叫我們的智慧快取字典
    stock_map = load_tw_stock_names()
    
    # 2. 直接去字典找 (支援「中文」與「純數字」)
    if input_str in stock_map and isinstance(stock_map[input_str], str) and ("." in stock_map[input_str]):
        return stock_map[input_str]
        
    # 3. 真的找不到，才盲猜 .TW
    if input_str.isdigit() and 4 <= len(input_str) <= 6:
        return f"{input_str}.TW"
        
    return None

def run_async_crawler(watchlist):
    """多執行緒抓取基本面數據引擎"""
    if not watchlist: 
        return pd.DataFrame()
        
    stock_names = load_tw_stock_names()
    data = []
    
    def fetch_data(ticker):
        cn_name = stock_names.get(ticker, "N/A")
        try:
            info = yf.Ticker(ticker).info
            return {
                "股票代號": ticker,
                "公司名稱": cn_name,
                "目前股價": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
                "本益比 (P/E)": info.get("trailingPE", "N/A"),
                "殖利率 (%)": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else "N/A",
                "營收成長率 (%)": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else "N/A"
            }
        except:
            return {
                "股票代號": ticker, "公司名稱": cn_name, "目前股價": "N/A", 
                "本益比 (P/E)": "N/A", "殖利率 (%)": "N/A", "營收成長率 (%)": "N/A"
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_data, watchlist)
        for res in results:
            data.append(res)
            
    return pd.DataFrame(data)

def run_market_screener(watchlist):
    """市場掃描器"""
    df = run_async_crawler(watchlist)
    return df