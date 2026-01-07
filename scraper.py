import requests
import pandas as pd
import time
import sys
import re  # ✅ 記得引入 re 套件來處理文字
from bs4 import BeautifulSoup

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- 1. 你的手動地點清單 ---
all_locations = {
    "F010": "基隆大武崙砲台停車場",
    "F022": "陽明山國家公園小油坑停車場",
    "F023": "陽明山國家公園擎天崗",
    "F011": "五分山",
    "F012": "石碇雲海國小",
    "F013": "烏來風景特定區",
    "F014": "觀霧森林遊樂區",
    "F019": "大雪山國家森林遊樂區",
    "F018": "武陵農場",
    "F020": "福壽山農場",
    "F021": "臺中都會公園",
    "F002": "小風口停車場",
    "F016": "新中橫塔塔加停車場",
    "F004": "臺大山地實驗農場",
    "F003": "鳶峰停車場",
    "F015": "阿里山遊樂區",
    "F017": "鹿林天文台",
    "F024": "七股海堤",
    "F025": "南瀛天文館",
    "F026": "臺南都會公園",
    "F007": "高雄梅山青年活動中心",
    "F009": "高雄都會公園",
    "F008": "藤枝森林遊樂區",
    "F005": "墾丁貓鼻頭",
    "F006": "墾丁龍磐公園",
    "F001": "太平山森林遊樂區",
}

# --- 2. 改良版爬蟲函式 (含紫外線格式修正) ---
def scrape_weekly_table(pid, location_name):
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/Week/{pid}_Week_PC.html"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return []
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. 處理表頭 (日期)
        thead = soup.find("thead")
        if not thead: return []
        dates = []
        date_row = thead.find_all("tr")[0].find_all("th")
        for th in date_row:
            text = th.get_text(strip=True)
            if not text or text == "日期": continue
            for _ in range(int(th.get('colspan', 1))): dates.append(text)
            
        # 2. 處理內容 (數據)
        tbody = soup.find("tbody")
        if not tbody: return []
        parsed_data = {}
        
        for row in tbody.find_all("tr"):
            th = row.find("th")
            if not th: continue
            row_name = th.get_text(strip=True)
            
            vals = []
            for td in row.find_all("td"):
                # --- A. 取值邏輯 ---
                img = td.find("img")
                tem_c = td.find("span", class_="tem-C") 
                
                if img:
                    val = img.get('title') or img.get('alt')
                elif tem_c:
                    val = tem_c.get_text(strip=True)
                else:
                    val = td.get_text(strip=True)
                
                # --- B. 判斷是否為「無資料」 ---
                if val == "-" or val == "" or val is None:
                    val = "未知"

                # --- C. ✅ 新增：紫外線格式修正 ---
                # 原始資料可能是 "2低量級"，我們要改成 "低量級(指數2)"
                if "紫外線" in row_name and val != "未知":
                    # 使用 Regex 分離數字和文字
                    # (\d+) 抓數字， (.*) 抓剩下的文字
                    match = re.match(r"^(\d+)(.*)$", val)
                    if match:
                        num = match.group(1)   # 例如 "2"
                        desc = match.group(2)  # 例如 "低量級"
                        val = f"{desc}(指數{num})" # 組合成 "低量級(指數2)"
                
                vals.append(val)
            
            parsed_data[row_name] = vals
            
        # 3. 轉置資料
        results = []
        for i in range(len(dates)):
            item = {
                "location": location_name, 
                "pid": pid, 
                "date": dates[i], 
                "time_desc": "白天" if i%2==0 else "晚上"
            }
            for k, v in parsed_data.items(): 
                item[k] = v[i] if i < len(v) else "未知"
            results.append(item)
            
        return results
    except Exception as e:
        print(f"❌ 爬取錯誤: {e}")
        return []

# --- 主程式 ---
if __name__ == "__main__":
    if not all_locations:
        print("❌ 請檢查地點清單是否為空！")
    else:
        print(f"🚀 開始爬取 {len(all_locations)} 個地點...")
        final_data = []
        
        count = 0
        for pid, name in all_locations.items():
            data = scrape_weekly_table(pid, name)
            if data:
                final_data.extend(data)
                count += 1
                print(f"   [{count}/{len(all_locations)}] {name} - 完成")
            else:
                print(f"   [{count}/{len(all_locations)}] {name} - 無資料")
            
            time.sleep(0.2) 

        if final_data:
            df = pd.DataFrame(final_data)
            df.to_csv("all_taiwan_star_forecast.csv", index=False, encoding="utf-8-sig")
            print(f"\n✅ 成功！已儲存 {len(final_data)} 筆資料")
            print("✨ 紫外線格式已統一修正為 '等級(數值)'")