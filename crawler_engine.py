import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests

# 🌟 內建急救小字典：就算政府網站當機，這些熱門股也絕對不會變成英文
STOCK_MAPPING = {
    "台積電": "2330.TW", "聯發科": "2454.TW", "鴻海": "2317.TW", "旺矽": "6223.TWO",
    "元大台灣50": "0050.TW", "國泰永續高股息": "00878.TW", "復華台灣科技優息": "00929.TW",
    "群創": "3481.TW", "長榮": "2603.TW", "陽明": "2609.TW", "萬海": "2615.TW",
    "富邦金": "2881.TW", "國泰金": "2882.TW", "中信金": "2891.TW", "玉山金": "2884.TW",
    "廣達": "2382.TW", "緯創": "3231.TW", "技嘉": "2376.TW", "英業達": "2356.TW"
}

def clean_stock_name(name):
    """🧹 名字淨水器：把又臭又長的官方全名洗成乾淨的簡稱"""
    if not name or name == "N/A": return "N/A"
    # 如果是全英文 (代表政府擋住了，Yahoo 抓的)，我們直接回傳，不要亂切
    if re.match(r'^[A-Za-z0-9\s\.\,\-]+$', name): return name
    
    # 🌟 核心黑科技：一秒斬斷所有冗長後綴！
    name = re.sub(r'(科技|工業|控股|金融控股|投資控股|建設|生物科技|股份有限公司|有限公司).*', '', name)
    name = re.sub(r'\(.*\)|（.*）', '', name) # 移除括號 (例如某些 KY 股)
    return name.strip()

def extract_id_name(item):
    """🔑 萬能鑰匙：自動破解政府 API 隨時亂改的欄位名稱"""
    stock_id = item.get("Code") or item.get("公司代號") or item.get("證券代號") or item.get("SecuritiesCompanyCode") or ""
    stock_name = item.get("Name") or item.get("公司簡稱") or item.get("證券名稱") or item.get("CompanyName") or item.get("PaperName") or ""
    # 套用淨水器
    return str(stock_id).strip(), clean_stock_name(str(stock_name).strip())

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    name_dict = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    
    urls = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "https://www.tpex.org.tw/openapi/v1/t13stk04"
    ]
    
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                for item in res.json():
                    stock_id, stock_name = extract_id_name(item)
                    if len(stock_id) >= 4 and stock_name:
                        suffix = ".TWO" if "tpex" in url else ".TW"
                        full_ticker = f"{stock_id}{suffix}"
                        name_dict[full_ticker] = stock_name
                        name_dict[stock_name] = full_ticker
                        name_dict[stock_id] = full_ticker
        except:
            continue

    # 就算政府網站當機，我們把急救小字典倒進去保底
    for cn_name, full_ticker in STOCK_MAPPING.items():
        if full_ticker not in name_dict:
            name_dict[full_ticker] = cn_name
            name_dict[cn_name] = full_ticker
            name_dict[full_ticker.split('.')[0]] = full_ticker 
            
    return name_dict

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

        if ticker in twse_funds:
            tw_pe = twse_funds[ticker].get("PE", "N/A")
            tw_dy = twse_funds[ticker].get("Yield", "N/A")
            tw_name = twse_funds[ticker].get("Name", "")
            
            if (cn_name == "N/A" or cn_name == "") and tw_name:
                cn_name = tw_name

            pe = tw_pe if tw_pe not in ["", "-", "0.00"] else "N/A"
            dy_str = tw_dy if tw_dy not in ["", "-", "0.00"] else "N/A"
        
        # 如果真的連名字都沒有，去求 Yahoo (這時會拿到英文)
        if cn_name == "N/A" or cn_name == "":
            try:
                info = tk.info
                cn_name = info.get("shortName", ticker)
            except:
                cn_name = ticker

        if pe == "N/A" or dy_str == "N/A":
            try:
                info = tk.info
                if pe == "N/A": pe = info.get("trailingPE", "N/A")
                if dy_str == "N/A": 
                    dy = info.get("dividendYield")
                    dy_str = round(dy * 100, 2) if dy else "N/A"
            except:
                pass
        
        # 🌟 出口端最後清洗：確保任何顯示出來的文字都是極致簡短乾淨的！
        cn_name = clean_stock_name(cn_name)

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