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

def extract_id_name(item):
    """🔑 萬能鑰匙：自動破解政府 API 隨時亂改的欄位名稱"""
    stock_id = item.get("Code") or item.get("公司代號") or item.get("證券代號") or item.get("SecuritiesCompanyCode") or ""
    stock_name = item.get("Name") or item.get("公司簡稱") or item.get("證券名稱") or item.get("CompanyName") or item.get("PaperName") or ""
    return str(stock_id).strip(), str(stock_name).strip()

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    name_dict = {}
    # 偽裝成真人瀏覽器
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    
    # 定義所有可能抓到股票名字的政府網址
    urls = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L", # 上市公司
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", # 上櫃公司
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", # 上市每日行情
        "https://www.tpex.org.tw/openapi/v1/t13stk04" # 上櫃每日行情
    ]
    
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                for item in res.json():
                    stock_id, stock_name = extract_id_name(item)
                    if len(stock_id) >= 4 and stock_name:
                        # 自動判斷是上市還上櫃 (依據來源網址)
                        suffix = ".TWO" if "tpex" in url else ".TW"
                        full_ticker = f"{stock_id}{suffix}"
                        name_dict[full_ticker] = stock_name
                        name_dict[stock_name] = full_ticker
                        name_dict[stock_id] = full_ticker
        except:
            continue

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
    """🤖 智慧尋標引擎"""
    if not user_input: return None
    user_input = str(user_input).strip().upper()
    
    for name, ticker in STOCK_MAPPING.items():
        if user_input == name or user_input in name:
            return ticker
            
    if user_input.endswith(".TW") or user_input.endswith(".TWO"):
        return user_input
        
    stock_map = load_tw_stock_names()
    if user_input in stock_map and isinstance(stock_map[user_input], str) and ("." in stock_map[user_input]):
        return stock_map[user_input]
        
    for key, value in stock_map.items():
        if "." in str(value) and (user_input in str(key)):
            return value

    if user_input.isdigit() or (user_input[:-1].isdigit() and user_input[-1].isalpha()):
        tw_ticker = f"{user_input}.TW"
        df_tw = yf.download(tw_ticker, period="1d", progress=False)
        if not df_tw.empty:
            return tw_ticker 
            
        two_ticker = f"{user_input}.TWO"
        df_two = yf.download(two_ticker, period="1d", progress=False)
        if not df_two.empty:
            return two_ticker 
            
    return None 

@st.cache_data(ttl=3600)
def load_twse_fundamentals():
    fund_dict = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for item in res.json():
                stock_id, stock_name = extract_id_name(item)
                if stock_id:
                    fund_dict[f"{stock_id}.TW"] = {
                        "Name": stock_name,
                        "PE": item.get("PEratio", "N/A"),
                        "Yield": item.get("DividendYield", "N/A")
                    }
    except: pass
    return fund_dict

def run_async_crawler(watchlist):
    """雙引擎爬蟲：先查證交所官方庫，再找 Yahoo 補漏"""
    if not watchlist: return pd.DataFrame()
    stock_names = load_tw_stock_names()
    twse_funds = load_twse_fundamentals()  
    data = []
    
    def fetch_data(ticker):
        cn_name = stock_names.get(ticker, "N/A")
        price = "N/A"
        pe = "N/A"
        dy_str = "N/A"
        
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="1d")
            if not hist.empty:
                price = round(hist['Close'].iloc[-1], 2)
        except:
            pass

        # 抓取基本面 (PE, 殖利率) 以及官方名稱
        if ticker in twse_funds:
            tw_pe = twse_funds[ticker].get("PE", "N/A")
            tw_dy = twse_funds[ticker].get("Yield", "N/A")
            tw_name = twse_funds[ticker].get("Name", "")
            
            # 如果中文名稱還是 N/A，試著用官方財報庫的名字
            if (cn_name == "N/A" or cn_name == "") and tw_name:
                cn_name = tw_name

            pe = tw_pe if tw_pe not in ["", "-", "0.00"] else "N/A"
            dy_str = tw_dy if tw_dy not in ["", "-", "0.00"] else "N/A"
        
        # 如果真的連名字都沒有，才去求 Yahoo (這時才會拿到英文)
        if cn_name == "N/A" or cn_name == "":
            try:
                info = tk.info
                cn_name = info.get("shortName", ticker)
            except:
                cn_name = ticker

        # 補漏 Yahoo 的基本面
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