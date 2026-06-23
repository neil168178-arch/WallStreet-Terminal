import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests

# 建立一個基礎的中文對照字典 (您可以隨時自己把喜歡的股票加進來)
STOCK_MAPPING = {
    "台積電": "2330.TW",
    "聯發科": "2454.TW",
    "鴻海": "2317.TW",
    "旺矽": "6223.TWO",
    "元大台灣50": "0050.TW",
    "國泰永續高股息": "00878.TW"
}

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

def resolve_ticker(user_input):
    """🤖 智慧尋標引擎：自動判斷上市 (.TW) 或上櫃 (.TWO)"""
    if not user_input: return None
    user_input = str(user_input).strip().upper()
    
    # 1. 字典反查：如果使用者輸入中文，直接從字典找
    for name, ticker in STOCK_MAPPING.items():
        if user_input == name or user_input in name:
            return ticker
            
    # 2. 完美輸入：如果使用者已經乖乖輸入 .TW 或 .TWO，直接放行
    if user_input.endswith(".TW") or user_input.endswith(".TWO"):
        return user_input
        
    # 從政府開放資料快取名單找尋精確配對
    stock_map = load_tw_stock_names()
    if user_input in stock_map and isinstance(stock_map[user_input], str) and ("." in stock_map[user_input]):
        return stock_map[user_input]
        
    for key, value in stock_map.items():
        if "." in str(value) and (user_input in str(key)):
            return value

    # 3. 🎯 核心黑科技：自動偵測上市或上櫃！
    # 如果使用者只輸入純數字 (例如 6223 或 2330) 或是 ETF (如 00929)
    if user_input.isdigit() or (user_input[:-1].isdigit() and user_input[-1].isalpha()):
        # 測試 A：去敲「上市」的門 (.TW)
        tw_ticker = f"{user_input}.TW"
        df_tw = yf.download(tw_ticker, period="1d", progress=False)
        if not df_tw.empty:
            return tw_ticker # 找到了！是上市股
            
        # 測試 B：去敲「上櫃」的門 (.TWO)
        two_ticker = f"{user_input}.TWO"
        df_two = yf.download(two_ticker, period="1d", progress=False)
        if not df_two.empty:
            return two_ticker # 找到了！是上櫃股
            
    return None # 真的找不到這檔股票

# ==========================================
# 🌟 獨家新增：直連台灣證券交易所官方財報庫
# ==========================================
@st.cache_data(ttl=3600)
def load_twse_fundamentals():
    """抓取證交所每日最新本益比與殖利率，徹底擺脫 Yahoo 限制"""
    fund_dict = {}
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            for item in res.json():
                code = str(item.get("Code", "")).strip()
                fund_dict[f"{code}.TW"] = {
                    "PE": item.get("PEratio", "N/A"),
                    "Yield": item.get("DividendYield", "N/A")
                }
    except Exception as e:
        print(f"證交所基本面獲取失敗: {e}")
    return fund_dict

def run_async_crawler(watchlist):
    """雙引擎爬蟲：先查證交所官方庫，再找 Yahoo 補漏"""
    if not watchlist: return pd.DataFrame()
    stock_names = load_tw_stock_names()
    twse_funds = load_twse_fundamentals()  # 載入官方資料庫
    data = []
    
    def fetch_data(ticker):
        cn_name = stock_names.get(ticker, "N/A")
        price = "N/A"
        pe = "N/A"
        dy_str = "N/A"
        
        # 1. 抓取最新股價 (使用最不會壞的 history 函數)
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="1d")
            if not hist.empty:
                price = round(hist['Close'].iloc[-1], 2)
        except:
            pass

        # 2. 優先向「台灣證交所官方庫」調閱本益比與殖利率
        if ticker in twse_funds:
            tw_pe = twse_funds[ticker].get("PE", "N/A")
            tw_dy = twse_funds[ticker].get("Yield", "N/A")
            # 濾掉虧損公司或未配息公司回傳的 "-" 符號
            pe = tw_pe if tw_pe not in ["", "-", "0.00"] else "N/A"
            dy_str = tw_dy if tw_dy not in ["", "-", "0.00"] else "N/A"
        
        # 3. 如果官方庫沒有 (例如上櫃股票)，再嘗試去 Yahoo 碰運氣
        if pe == "N/A" or dy_str == "N/A":
            try:
                info = tk.info
                if pe == "N/A": 
                    pe = info.get("trailingPE", "N/A")
                if dy_str == "N/A": 
                    dy = info.get("dividendYield")
                    dy_str = round(dy * 100, 2) if dy else "N/A"
            except:
                pass

        return {
            "代號": ticker, "名稱": cn_name,
            "股價": price, "本益比": pe, "殖利率(%)": dy_str
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(fetch_data, watchlist):
            data.append(res)
            
    return pd.DataFrame(data)

def run_market_screener(watchlist):
    return run_async_crawler(watchlist)