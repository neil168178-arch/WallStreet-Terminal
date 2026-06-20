<div align="center">

# 🚀 Wall Street Quant Terminal <br> (華爾街量化終端機 SaaS)

**將機構級的量化分析、AI 情緒解讀與動態風控，賦武於每一位獨立投資人。**

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram_Bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)

</div>

---

## 💡 專案簡介 (About The Project)

**Wall Street Quant Terminal** 是一套專為台股/美股投資人打造的全方位量化交易平台。
市面上的看盤軟體大多只提供落後的技術指標，而本系統完美整合了 **Supabase 雲端資料庫**、**Google Gemini AI 語意分析** 以及 **Telegram 自動推播機器人**，讓您擁有與華爾街基金經理人平起平坐的分析大腦。

系統強調「關注點分離」與「極致的 UI/UX 體驗」，內建全市場 2000+ 檔股票的自動中文化字典，無論是剛入門的散戶還是資深寬客 (Quant)，都能無痛上手。

---

## 🔥 核心功能 (Core Features)

* **🔐 企業級多租戶資料庫**：內建 Supabase 驗證與 RLS 保險箱，使用者的 API 金鑰與投資組合絕對加密隔離。
* **🏆 多因子量化評分引擎**：自動抓取全市場財報與技術面，以 `(價值 40% + 品質 30% + 動能 30%)` 演算法為股票進行 PR 值海選排名。
* **⏳ 機構級回測與盲測 (OOS)**：不僅提供完整的歷史交易明細，更內建「參數熱力圖 (Grid Search)」與「防過度擬合盲測」，幫您找出真正的神級參數。
* **🧠 AI 新聞情緒解析**：一鍵抓取 Google News 最新報導，交由 Gemini 2.5 Flash 進行 NLP 解析，輸出 0-100 的極端情緒儀表板與懶人包。
* **💰 ATR 動態資金控管**：再也不用憑感覺下單。系統自動根據個股近期真實波動幅度 (ATR)，為您精算「絕對安全」的建議買進股數。
* **✈️ Telegram 盤後雷達**：一鍵掃描您的觀察名單，當觸發均線交叉、MACD 爆發等訊號時，零延遲推播至您的手機。

---

## 🏗️ 系統架構 (Architecture)

本系統採用高度模組化 (Modular) 設計，確保未來擴充性與易維護性：

* `app.py`: 前端總指揮，負責 Streamlit UI 渲染與頁面路由。
* `render_engine.py`: 全局 UI 攔截器，負責數據表中文化、數值置中與千分位格式化。
* `data_engine.py` / `macro_engine.py`: 負責金融數據與總經指標獲取 (yfinance, FRED)。
* `ranking_engine.py`: 內建全台股 2000+ 字典的極速多執行緒評分引擎。
* `backtest_engine.py` / `strategy_engine.py`: 核心交易邏輯與向量化回測運算。
* `news_engine.py`: Google RSS 爬蟲與 Gemini Prompt Engineering 介接。
* `notification_engine.py`: Telegram 官方 API 異步推播整合。

---

## 🚀 快速啟動 (Quick Start)

想要在本地端運行這套終端機？請跟著以下步驟：

### 1. 安裝環境與套件
請確保您的電腦已安裝 Python 3.9 以上版本。
```bash
git clone [https://github.com/您的帳號/wall-street-terminal.git](https://github.com/您的帳號/wall-street-terminal.git)
cd wall-street-terminal
pip install -r requirements.txt