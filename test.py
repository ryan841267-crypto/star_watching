import requests
from bs4 import BeautifulSoup
import sys

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def debug_scrape(pid):
    # 這就是你截圖中顯示的正確網址
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/Week/{pid}_Week_PC.html"
    print(f"🚀 測試爬取: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"📡 HTTP 狀態碼: {response.status_code}") # 預期是 200
        
        response.encoding = 'utf-8'
        html_content = response.text
        
        # 1. 檢查 HTML 是否有內容
        if not html_content.strip():
            print("❌ 警告：抓到的 HTML 是空的！")
            return

        # 2. 印出前 500 字來檢查
        print("\n📄 HTML 內容預覽 (前 500 字):")
        print("-" * 50)
        print(html_content[:500])
        print("-" * 50)
        
        # 3. 檢查表格 ID 是否存在
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table") # 先不指定 ID，抓抓看有沒有任何表格
        
        if table:
            print(f"\n✅ 成功找到一個表格！")
            print(f"🆔 表格 ID 是: {table.get('id', '沒有 ID')}") # 看看它的 ID 到底是什麼
            print(f"📋 Class 是: {table.get('class', '沒有 Class')}")
        else:
            print("\n❌ 糟糕，BeautifulSoup 說裡面完全沒有 <table> 標籤")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

# --- 執行測試 ---
if __name__ == "__main__":
    debug_scrape("F022") # 測試合歡山