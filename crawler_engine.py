import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    name_dict = {}
    try:
        res_twse = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", timeout=10)
        if res_twse.status_code == 200:
            for item in res_twse.json():
                stock_id = str(item.get("公司代號", "")).strip()
                stock_name = str(item.get("公司簡稱", item.get("公司名稱", ""))).strip()
                if len(stock_id) >= 4:
                    name_dict[f"{stock_id}.TW"] = stock_name
                    name_dict[stock_name] = f"{stock_id}.TW"
                    name_dict[stock_id] = f"{stock_id}.TW"
                    
        res_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", timeout=10)
        if res_tpex.status_code == 200:
            for item in res_tpex.json():
                stock_id = str(item.get("公司代號", "")).strip()
                stock_name = str(item.get("公司簡稱", item.get("公司名稱", ""))).strip()
                if len(stock_id) >= 4:
                    name_dict[f"{stock_id}.TWO"] = stock_name
                    name_dict[stock_name] = f"{stock_id}.TWO"
                    name_dict[stock_id] = f"{stock_id}.TWO"
    except: pass

    try:
        res_all_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10)
        if res_all_twse.status_code == 200:
            for item in res_all_twse.json():
                stock_id = str(item.get("證券代號", "")).strip()
                stock_name = str(item.get("證券名稱", "")).strip()
                full_ticker = f"{stock_id}.TW"
                if full_ticker not in name_dict and len(stock_id) >= 4:
                    name_dict[full_ticker] = stock_name
                    name_dict[stock_name] = full_ticker
                    name_dict[stock_id] = full_ticker
                    
        res_all_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/t13stk04", timeout=10)
        if res_all_tpex.status_code == 200:
            for item in res_all_tpex.json():
                stock_id = str(item.get("SecuritiesCompanyCode", "")).strip()
                stock_name = str(item.get("PaperName", "")).strip()
                full_ticker = f"{stock_id}.TWO"
                if full_ticker not in name_dict and len(stock_id) >= 4:
                    name_dict[full_ticker] = stock_name
                    name_dict[stock_name] = full_ticker
                    name_dict[stock_id] = full_ticker
    except: pass

    fallback = _get_fallback_stock_map()
    for k, v in fallback.items():
        if k not in name_dict:
            name_dict[k] = v
            
    return name_dict

def _get_fallback_stock_map():
    base_map = {
        "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "3481.TW": "群創",
        "0050.TW": "元大台灣50", "00878.TW": "國泰永續高股息", "00929.TW": "復華台灣科技優息"
    }
    res = {}
    for full_ticker, cn_name in base_map.items():
        res[full_ticker] = cn_name
        res[cn_name] = full_ticker
        res[full_ticker.split('.')[0]] = full_ticker 
    return res

def resolve_ticker(input_str):
    if not input_str: return None
    input_str = input_str.strip()
    if re.match(r'^\d{4,6}[A-Z]?\.TW[O]?$', input_str.upper()): return input_str.upper()
    stock_map = load_tw_stock_names()
    if input_str in stock_map and isinstance(stock_map[input_str], str) and ("." in stock_map[input_str]): return stock_map[input_str]
    for key, value in stock_map.items():
        if "." in str(value) and (input_str in str(key)): return value
    if re.match(r'^\d{4,6}[A-Za-z]?$', input_str): return f"{input_str.upper()}.TW"
    return None

def run_async_crawler(watchlist):
    """🌟 強化防彈版：解決 Yahoo API N/A 問題"""
    if not watchlist: return pd.DataFrame()
    stock_names = load_tw_stock_names()
    data = []
    
    def fetch_data(ticker):
        cn_name = stock_names.get(ticker, "N/A")
        try:
            tk = yf.Ticker(ticker)
            
            # 🛡️ 防線 1: 直接去歷史 K 線抓最新價格 (最不容易壞)
            hist = tk.history(period="1d")
            price = round(hist['Close'].iloc[-1], 2) if not hist.empty else "N/A"
            
            # 🛡️ 防線 2: 嘗試抓取基本面 (用 try 包住，避免 yfinance 當機)
            try:
                info = tk.info
                pe = info.get("trailingPE", "N/A")
                dy = info.get("dividendYield")
                dy_str = round(dy * 100, 2) if dy else "N/A"
            except:
                pe, dy_str = "N/A", "N/A"

            return {
                "代號": ticker, "名稱": cn_name,
                "股價": price, "本益比": pe, "殖利率(%)": dy_str
            }
        except Exception as e:
            return {"代號": ticker, "名稱": cn_name, "股價": "N/A", "本益比": "N/A", "殖利率(%)": "N/A"}

    # 🌟 降低多線程數量 (從 10 降到 5)，避免瞬間送出太多請求被 Yahoo 封鎖
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(fetch_data, watchlist):
            data.append(res)
            
    return pd.DataFrame(data)

def run_market_screener(watchlist):
    return run_async_crawler(watchlist)