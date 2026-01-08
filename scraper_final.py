import requests
import pandas as pd
import time
import sys
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


# 用來處理 Quick Reply 的區域分類
# 區域分類字典 (用於 LINE Bot 選單邏輯)
# 邏輯：北中南三區，剛好符合 LINE Carousel 上限 (10個)
region_map = {
    "北部": [
        "F010", # 基隆
        "F022", "F023", # 台北
        "F011", "F012", "F013", # 新北
        "F001"  # 宜蘭
    ],
    "中部": [
        "F014", # 苗栗
        "F019", "F018", "F020", "F021", # 台中
        "F002", "F016", "F004", "F003"  # 南投
    ],
    "南部": [
        "F015", "F017", # 嘉義
        "F024", "F025", "F026", # 台南
        "F007", "F009", "F008", # 高雄
        "F005", "F006"  # 屏東
    ]
}

# 反向查詢 (如果需要從 PID 找區域名稱)
# 你的 all_locations 已經有了 PID 對應名稱，這部分維持原樣即可
# --- 1. 全台觀星地點清單 (共用) ---
all_locations = {
    "F010": "基隆大武崙砲台停車場", "F022": "陽明山國家公園小油坑停車場", "F023": "陽明山國家公園擎天崗",
    "F011": "五分山", "F012": "石碇雲海國小", "F013": "烏來風景特定區", "F014": "觀霧森林遊樂區",
    "F019": "大雪山國家森林遊樂區", "F018": "武陵農場", "F020": "福壽山農場", "F021": "臺中都會公園",
    "F002": "小風口停車場", "F016": "新中橫塔塔加停車場", "F004": "臺大山地實驗農場", "F003": "鳶峰停車場",
    "F015": "阿里山遊樂區", "F017": "鹿林天文台", "F024": "七股海堤", "F025": "南瀛天文館",
    "F026": "臺南都會公園", "F007": "高雄梅山青年活動中心", "F009": "高雄都會公園", "F008": "藤枝森林遊樂區",
    "F005": "墾丁貓鼻頭", "F006": "墾丁龍磐公園", "F001": "太平山森林遊樂區",
}

# ==========================================
# 功能 A：每週預報 (CSV 讀取)
# ==========================================

# 爬蟲函式 (更新 CSV 用)
def scrape_weekly_table(pid, location_name):
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/Week/{pid}_Week_PC.html"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return []
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        thead = soup.find("thead")
        if not thead: return []
        dates = []
        date_row = thead.find_all("tr")[0].find_all("th")
        for th in date_row:
            text = th.get_text(strip=True)
            if not text or text == "日期": continue
            for _ in range(int(th.get('colspan', 1))): dates.append(text)
            
        tbody = soup.find("tbody")
        if not tbody: return []
        parsed_data = {}
        
        for row in tbody.find_all("tr"):
            th = row.find("th")
            if not th: continue
            row_name = th.get_text(strip=True)
            vals = []
            for td in row.find_all("td"):
                img = td.find("img")
                tem_c = td.find("span", class_="tem-C") 
                val = img.get('title') or img.get('alt') if img else (tem_c.get_text(strip=True) if tem_c else td.get_text(strip=True))
                if val in ["-", "", None]: val = "未知"
                if "紫外線" in row_name and val != "未知":
                    match = re.match(r"^(\d+)(.*)$", val)
                    if match: val = f"{match.group(2)}(指數{match.group(1)})"
                vals.append(val)
            parsed_data[row_name] = vals
            
        results = []
        for i in range(len(dates)):
            item = {"location": location_name, "pid": pid, "date": dates[i], "時間": "白天" if i % 2 == 0 else "晚上"}
            for k, v in parsed_data.items(): 
                if k == "時間": continue
                item[k] = v[i] if i < len(v) else "未知"
            results.append(item)
        return results
    except Exception as e:
        print(f"❌ 爬取錯誤 ({location_name}): {e}")
        return []

# 更新 CSV 檔案 (可排程執行)
def update_weekly_csv():
    file_name = "all_taiwan_star_forecast.csv"
    print(f"🚀 開始更新每週預報資料 (共 {len(all_locations)} 處)...")
    final_data = []
    for pid, name in all_locations.items():
        data = scrape_weekly_table(pid, name)
        if data: final_data.extend(data)
        time.sleep(0.2)
    
    if final_data:
        new_df = pd.DataFrame(final_data)
        if os.path.exists(file_name) and os.path.getsize(file_name) > 0:
            try:
                final_df = pd.concat([pd.read_csv(file_name, encoding="utf-8-sig"), new_df], ignore_index=True).drop_duplicates(subset=['location', 'date', '時間'], keep='last')
            except: final_df = new_df
        else: final_df = new_df
        final_df.to_csv(file_name, index=False, encoding="utf-8-sig")
        print(f"✅ CSV 更新完成！目前共有 {len(final_df)} 筆數據。")

# 查詢函式 (回傳字串 - 格式已調整)
def get_weekly_star_info(user_input):
    file_name = "all_taiwan_star_forecast.csv"
    try:
        if not os.path.exists(file_name): return "⚠️ 找不到資料檔，請聯繫管理員更新資料庫。"
        df = pd.read_csv(file_name, encoding="utf-8-sig")
        # 僅篩選晚上
        target_df = df[(df['location'].str.contains(user_input)) & (df['時間'] == "晚上")].copy()
        
        if target_df.empty: return f"找不到「{user_input}」的預報資料。"

        tz_taiwan = timezone(timedelta(hours=8))
        today = datetime.now(tz_taiwan).date()
        this_year = datetime.now(tz_taiwan).year

        def is_future(date_str):
            try: return datetime.strptime(f"{this_year}/{date_str[:5]}", "%Y/%m/%d").date() >= today
            except: return True
            
        target_df = target_df[target_df['date'].apply(is_future)]
        data_list = target_df.head(7).to_dict('records')
        
        if not data_list: return f"目前沒有 {user_input} 未來一週的資料。"

        all_blocks = []
        for item in data_list:
            score = 1
            weather = item.get('天氣狀況', '未知')
            
            # --- 分數計算 ---
            if "晴" in weather: score += 2
            try:
                if int(item.get('最高溫', 0)) > 15: score += 1
                if 20 <= int(item.get('最高溫', 0)) <= 25: score += 1
            except: pass
            try:
                if int(re.findall(r'\d+', str(item.get('蒲福風級', '0')))[-1]) >= 5: score -= 1
            except: pass
            stars = "⭐" * max(1, min(5, score))

            # --- 綜合評估 ---
            if "晴" not in weather:
                eval_msg = "今晚不適合觀星。"
            else:
                try:
                    fl = int(item.get('體感最低溫', 20))
                    if fl < 15: eval_msg = "天氣寒冷，外出觀星建議多穿幾件保暖衣物！"
                    elif 15 <= fl < 20: eval_msg = "天氣稍涼，外出觀星建議穿件薄外套！"
                    elif 20 <= fl <= 25: eval_msg = "天氣舒適，絕佳觀星日！"
                    else: eval_msg = "適合觀星的溫熱夜晚！"
                except: eval_msg = "請注意現場天氣變化。"
                
                # 疊加風力警示
                try:
                    if int(re.findall(r'\d+', str(item.get('蒲福風級', '0')))[-1]) >= 5:
                        eval_msg += " (另外今晚風力較強，行經視線昏暗處請小心！)"
                except: pass
                
                

            # --- 格式組裝 (直列式) ---
            res = [
                f"📅 {item['date']} ({item['時間']})",
                f"天氣：{weather}",
                f"氣溫：{item.get('最低溫', '?')}~{item.get('最高溫', '?')}°C",
                f"體感：{item.get('體感最低溫', '?')}~{item.get('體感最高溫', '?')}°C",
                f"降雨：{item.get('降雨機率', '未知')}",
                f"觀星推薦指數：{stars}",
                f"📝 綜合評估：{eval_msg}"
            ]
            all_blocks.append("\n".join(res))
            
        header = f"🌌 【{user_input}】未來一週觀星指南\n\n"
        tail = "\n\n----------------\n🔔 溫馨提醒：當日可再確認晴朗的晚間時段哦~\n\n"
        return header + "\n\n----------------\n".join(all_blocks) + tail
    except Exception as e: return f"❌ 錯誤：{str(e)}"


# ==========================================
# 功能 B：臨時興起 (72hr 即時爬蟲)
# ==========================================

def format_time_ranges(time_list):
    if not time_list: return ""
    hours = [int(t.split(':')[0]) for t in time_list]
    processed = [h + 24 if h <= 5 and any(p >= 18 for p in hours) else h for h in hours]
    
    ranges = []
    start_h = prev_h = processed[0]
    for i in range(1, len(processed)):
        curr = processed[i]
        if curr == prev_h + 1: prev_h = curr
        else:
            ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
            start_h = prev_h = curr
    ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
    return "、".join(ranges)

# 查詢函式 (即時爬蟲)
def get_impromptu_star_info(pid, location_name):
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/3hr/{pid}_3hr_PC.html"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        raw_html = f"<table>{resp.text}</table>" if "<table" not in resp.text else resp.text
        soup = BeautifulSoup(raw_html, "html.parser")
        
        date_map = {th.get("id").split("_")[-1]: th.get_text(strip=True)[:5] 
                    for th in soup.find_all("th") if th.get("id") and "PC3_D" in th.get("id") and "H" not in th.get("id") and th.get("id") != "PC3_D"}
        time_row = soup.find("tr", class_="time")
        time_ids = [th.get('id') for th in time_row.find_all("th")[1:] if th.get('id')]
        time_full_labels = {tid: f"{date_map[next(dk for dk in date_map if dk in tid)]} {time_row.find('th', id=tid).get_text(strip=True)}" for tid in time_ids}

        master_data = {tid: {} for tid in time_ids}
        for row in soup.find_all("tr"):
            th = row.find("th")
            if not th or "時間" in th.get_text(): continue
            title = th.get_text(strip=True)
            for td in row.find_all("td"):
                h_attr = td.get('headers', "")
                val = td.find("img").get('title') if td.find("img") else (td.find("span", class_="tem-C").get_text(strip=True) if td.find("span", class_="tem-C") else td.get_text(strip=True))
                for tid in time_ids:
                    if tid in h_attr: master_data[tid][title] = val

        perfect_times, cloudy_times = [], []
        for tid in time_ids[:24]:
            time_str = time_full_labels[tid].split(" ")[1]
            hour = int(time_str.split(":")[0])
            if hour >= 18 or hour <= 5:
                w = master_data[tid].get("天氣狀況", "未知")
                if "晴" in w: perfect_times.append(time_str)
                elif "多雲" in w: cloudy_times.append(time_str)

        if perfect_times:
            return f"🔭 【{location_name}】觀星建議：😊 \n太棒了，今晚最適合觀星的時段為：{format_time_ranges(perfect_times)}"
        elif cloudy_times:
            return f"🔭 【{location_name}】觀星建議：😐 \n今晚雲量較多，可碰運氣的時段為：{format_time_ranges(cloudy_times)}"
        else:
            return f"🔭 【{location_name}】觀星建議：😭 \n今晚不適合觀星，請好好睡覺。"
    except Exception as e:
        return f"❌ 系統錯誤: {str(e)}"

# ==========================================
# 主程式測試區
# ==========================================
if __name__ == "__main__":
    # 1. 第一次執行建議跑一次更新，之後可註解掉
    update_weekly_csv() 
    
    print("\n--------- 模擬 LINE Bot 使用者操作 ---------")
    
    # 使用者選擇情境 A：規劃未來
    print("🔹 用戶點選：未來一週觀星指南 -> 選擇：陽明山小油坑")
    print(get_weekly_star_info("小油坑"))
    
    print("\n-------------------------------------------")
    
    # 使用者選擇情境 B：臨時出發
    print("🔹 用戶點選：臨時興起去觀星 -> 選擇：鹿林天文台")
    # 注意：這裡需要傳入 PID (F017)
    print(get_impromptu_star_info("F017", "鹿林天文台"))