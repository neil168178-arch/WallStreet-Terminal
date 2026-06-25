import pandas as pd
import yfinance as yf
import re
import streamlit as st
import concurrent.futures
import requests
from supabase import create_client

@st.cache_data(ttl=3600)
def load_cloud_dictionary():
    """☁️ 從 Supabase 下載全站共用的雲端股票字典"""
    cloud_map = {}
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        sb = create_client(url, key)
        res = sb.table("global_stock_dictionary").select("*").execute()
        if res.data:
            for row in res.data:
                cloud_map[row['cn_name']] = row['ticker']
    except Exception as e:
        print(f"雲端字典讀取失敗: {e}")
    return cloud_map

def get_combined_mapping():
    """🤝 將本地急救箱與雲端字典完美融合"""
    base_map = {
        "台積電": "2330.TW", "聯發科": "2454.TW", "鴻海": "2317.TW",
        "元大台灣50": "0050.TW", "國泰永續高股息": "00878.TW", "復華台灣科技優息": "00929.TW"
    }
    cloud_map = load_cloud_dictionary()
    base_map.update(cloud_map) # 雲端字典擁有最高覆蓋權
    return base_map

def clean_stock_name(name):
    """🧹 名字淨水器"""
    if not name or name == "N/A": return "N/A"
    if re.match(r'^[A-Za-z0-9\s\.\,\-]+$', name): return name
    name = re.sub(r'(科技|工業|控股|金融控股|投資控股|建設|生物科技|股份有限公司|有限公司).*', '', name)
    name = re.sub(r'\(.*\)|（.*）', '', name)
    return name.strip()

def extract_id_name(item):
    stock_id = item.get("Code") or item.get("公司代號") or item.get("證券代號") or item.get("SecuritiesCompanyCode") or ""
    stock_name = item.get("Name") or item.get("公司簡稱") or item.get("證券名稱") or item.get("CompanyName") or item.get("PaperName") or ""
    return str(stock_id).strip(), clean_stock_name(str(stock_name).strip())

@st.cache_data(ttl=3600*24)
def load_tw_stock_names():
    name_dict = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        except: continue
            
    return name_dict

def resolve_ticker(user_input):
    """🤖 智慧尋標引擎"""
    if not user_input: return None
    user_input = str(user_input).strip().upper()
    
    # 1. 優先查核我們的雲端無敵字典
    combined_mapping = get_combined_mapping()
    for name, ticker in combined_mapping.items():
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
        if not df_tw.empty: return tw_ticker 
            
        two_ticker = f"{user_input}.TWO"
        df_two = yf.download(two_ticker, period="1d", progress=False)
        if not df_two.empty: return two_ticker 
            
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
    if not watchlist: return pd.DataFrame()
    stock_names = load_tw_stock_names()
    twse_funds = load_twse_fundamentals()  
    data = []
    
    # 偷偷把雲端字典也倒進去，確保名字絕對是中文
    combined_mapping = get_combined_mapping()
    inv_cloud_map = {v: k for k, v in combined_mapping.items()}
    
    def format_number(val):
        """🌟 數值淨水器：最多保留3位小數，並且把多餘的0切乾淨"""
        try:
            v = float(val)
            # 轉成最多3位小數的字串，例如 "25.000" 或 "4.350"
            formatted = f"{v:.3f}"
            # 去掉尾部的 0 (變成 "25." 或 "4.35")，再去掉可能剩下的 "." (變成 "25")
            formatted = formatted.rstrip('0').rstrip('.')
            # 萬一原數值是 0.0，處理後變空字串，我們補回 "0"
            return "0" if formatted == "" else formatted
        except:
            return str(val)

    def fetch_data(ticker):
        cn_name = inv_cloud_map.get(ticker, stock_names.get(ticker, "N/A"))
        price, pe, dy_str = "N/A", "N/A", "N/A"
        change_pct = "N/A"  # 🌟 終於加上漲跌幅變數了！
        
        try:
            tk = yf.Ticker(ticker)
            # 🌟 為了算漲跌幅，改為抓取近 5 天資料
            hist = tk.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                price = current_price
                change_pct = ((current_price - prev_price) / prev_price) * 100
            elif not hist.empty and len(hist) == 1:
                price = hist['Close'].iloc[-1]
        except: pass

        if ticker in twse_funds:
            tw_pe = twse_funds[ticker].get("PE", "N/A")
            tw_dy = twse_funds[ticker].get("Yield", "N/A")
            tw_name = twse_funds[ticker].get("Name", "")
            
            if (cn_name == "N/A" or cn_name == "") and tw_name:
                cn_name = tw_name
            pe = tw_pe if tw_pe not in ["", "-", "0.00"] else "N/A"
            dy_str = tw_dy if tw_dy not in ["", "-", "0.00"] else "N/A"
        
        if cn_name == "N/A" or cn_name == "":
            try: cn_name = tk.info.get("shortName", ticker)
            except: cn_name = ticker

        if pe == "N/A" or dy_str == "N/A":
            try:
                info = tk.info
                if pe == "N/A": pe = info.get("trailingPE", "N/A")
                if dy_str == "N/A": 
                    dy = info.get("dividendYield")
                    dy_str = dy * 100 if dy else "N/A"
            except: pass
        
        cn_name = clean_stock_name(cn_name)

        # 🌟 套用淨水器，完美清洗所有醜醜的數字
        price = format_number(price)
        change_pct = format_number(change_pct)
        pe = format_number(pe)
        dy_str = format_number(dy_str)

        return {
            "代號": ticker, 
            "名稱": cn_name, 
            "股價": price, 
            "漲跌幅(%)": change_pct, # 🌟 交給網頁前端去染色的關鍵情報！
            "本益比": pe, 
            "殖利率(%)": dy_str
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(fetch_data, watchlist): data.append(res)
            
    return pd.DataFrame(data)

def run_market_screener(watchlist):
    return run_async_crawler(watchlist)