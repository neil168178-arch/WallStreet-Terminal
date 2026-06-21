import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    """雙引擎數據源：同時抓取「公司簡稱」與「所有證券(含ETF)」"""
    name_dict = {}
    
    # ================= 引擎 A：抓取一般上市櫃公司 (確保精準中文簡稱) =================
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
    except Exception as e:
        print(f"引擎 A 獲取失敗: {e}")

    # ================= 引擎 B：抓取全市場證券 (涵蓋所有 ETF、ETN) =================
    try:
        res_all_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10)
        if res_all_twse.status_code == 200:
            for item in res_all_twse.json():
                stock_id = str(item.get("證券代號", "")).strip()
                stock_name = str(item.get("證券名稱", "")).strip()
                full_ticker = f"{stock_id}.TW"
                # 如果字典裡還沒有，代表它是 ETF 或其他證券，把它加進去！
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
    except Exception as e:
        print(f"引擎 B 獲取失敗: {e}")

    # ================= 備用安全電源 =================
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
    """強化的股票代號翻譯引擎"""
    if not input_str: return None
    input_str = input_str.strip()
    
    if re.match(r'^\d{4,6}[A-Z]?\.TW[O]?$', input_str.upper()):
        return input_str.upper()
        
    stock_map = load_tw_stock_names()
    
    # 支援精準匹配
    if input_str in stock_map and isinstance(stock_map[input_str], str) and ("." in stock_map[input_str]):
        return stock_map[input_str]
        
    # 支援模糊匹配 (例如輸入"美債"自動找出對應ETF)
    for key, value in stock_map.items():
        if "." in str(value) and (input_str in str(key)):
            return value
            
    # 盲猜防呆 (支援含有英文字母的 ETF 代號如 00679B)
    if re.match(r'^\d{4,6}[A-Za-z]?$', input_str):
        return f"{input_str.upper()}.TW"
        
    return None

def run_async_crawler(watchlist):
    """多執行緒抓取基本面數據引擎"""
    if not watchlist: return pd.DataFrame()
    stock_names = load_tw_stock_names()
    data = []
    
    def fetch_data(ticker):
        cn_name = stock_names.get(ticker, "N/A")
        try:
            info = yf.Ticker(ticker).info
            return {
                "代號": ticker, "名稱": cn_name,
                "股價": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
                "本益比": info.get("trailingPE", "N/A"),
                "殖利率(%)": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else "N/A"
            }
        except:
            return {"代號": ticker, "名稱": cn_name, "股價": "N/A", "本益比": "N/A", "殖利率(%)": "N/A"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(fetch_data, watchlist):
            data.append(res)
            
    return pd.DataFrame(data)