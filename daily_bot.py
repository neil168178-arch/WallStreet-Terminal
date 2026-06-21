import os
import pandas as pd
from supabase import create_client, Client
from notification_engine import run_daily_signal_scanner

def is_etf_ticker(ticker):
    if not ticker: return False
    tk = ticker.split('.')[0]
    if tk.startswith('00') or not tk.isdigit(): return True
    return False

def main():
    print("🤖 [SaaS 中央伺服器] 啟動全站用戶雷達巡邏...")

    # 從 GitHub 保險箱拿出「上帝鑰匙」
    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not service_key:
        print("❌ 錯誤：找不到環境變數，請確認 GitHub Secrets 是否設定正確。")
        return

    # 1. 使用上帝鑰匙連線 (無須帳號密碼，直接擁有全站最高讀取權限)
    sb = create_client(url, service_key)
    print("✅ 上帝視角連線成功，準備撈取全站用戶資料...")

    # 2. 抓出全站「所有」有設定 Telegram 的用戶設定
    res_settings = sb.table("user_settings").select("*").execute()
    all_users = res_settings.data

    if not all_users:
        print("⚠️ 目前全站沒有任何用戶設定 Telegram 推播。")
        return

    print(f"👥 偵測到 {len(all_users)} 位活躍推播用戶，開始逐一運算...")

    # 3. 迴圈遍歷每一個用戶，幫他們量身打造推播
    for user in all_users:
        user_id = user.get("user_id")
        tg_token = user.get("tg_token")
        tg_chat_id = user.get("tg_chat_id")

        if not tg_token or not tg_chat_id:
            continue # 如果這個用戶沒填金鑰，就跳過他

        print(f"\n--- 處理用戶: {user_id[:8]}... ---")

        # 抓取「這個用戶」專屬的觀察名單
        res_watch = sb.table("watchlists").select("ticker").eq("user_id", user_id).execute()
        user_tickers = [row['ticker'] for row in res_watch.data]
        
        # 過濾出股票 (ETF 通常不適用短線雷達)
        stock_watchlist = [t for t in user_tickers if not is_etf_ticker(t)]

        if not stock_watchlist:
            print(f"⚠️ 該用戶沒有股票觀察名單，略過。")
            continue

        print(f"🔍 掃描名單：{stock_watchlist}")
        
        # 啟動運算引擎，並把結果直接發送到「該用戶」的 Telegram
        # 預設使用最強的 'combined' (多因子濾網) 策略進行全盤掃描
        success, msg = run_daily_signal_scanner(stock_watchlist, 'combined', tg_token, tg_chat_id)
        
        if success:
            print(f"✅ 已成功推播給該用戶！")
        else:
            print(f"⚠️ 推播完成，但無觸發訊號或發生錯誤。")

    print("\n🎉 [SaaS 中央伺服器] 今日全站自動推播任務圓滿完成！")

if __name__ == "__main__":
    main()