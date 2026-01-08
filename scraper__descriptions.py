import requests
import json
import time
import sys
from bs4 import BeautifulSoup

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

# 確保引用你的地點清單
from scraper_final import all_locations

def scrape_description(pid, location_name):
    # 💡 修正後的正確網址：去掉 _PC
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/Detail/{pid}_Detail.html"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cwa.gov.tw/V8/C/L/StarView/StarView.html"
    }

    try:
        # 加入 timestamp 參數模擬瀏覽器行為 (雖非必要但較保險)
        params = {"T": int(time.time())}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f" ⚠️ {location_name} ({pid}) 請求失敗 (Code: {response.status_code})")
            return "目前暫無詳細介紹。"
            
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 尋找簡介區塊 (氣象局有時候用 Detail_MOD，有時候可能結構微調，這裡通抓)
        # 先嘗試抓 id="Detail_MOD"
        detail_div = soup.find("div", id="Detail_MOD")
        
        # 如果 id 抓不到，嘗試直接抓內文的 p (防呆機制)
        if not detail_div:
            detail_div = soup
            
        p_tags = detail_div.find_all("p")
        if p_tags:
            # 合併多段文字，去除多餘空白
            desc = "\n".join([p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)])
            if len(desc) > 5: # 確保抓到的不是空字串
                return desc
        
        return "目前暫無詳細介紹。"
    except Exception as e:
        print(f" ❌ {location_name} 發生錯誤: {e}")
        return "資料讀取失敗。"

if __name__ == "__main__":
    print("🚀 最終嘗試：爬取全台景點簡介 (修正檔名)...")
    descriptions = {}
    
    for pid, name in all_locations.items():
        desc = scrape_description(pid, name)
        descriptions[pid] = desc
        # 印出前 10 個字檢查有沒有抓對
        print(f" ✅ {name}: {desc[:10]}...") 
        time.sleep(0.5)
        
    with open("spot_descriptions.json", "w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 簡介抓取完成！請檢查 spot_descriptions.json")