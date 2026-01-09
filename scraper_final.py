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

# --- 關鍵修正：加上 Referer 偽裝成是從氣象局網站發出的請求 ---
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cwa.gov.tw/V8/C/L/StarView/StarView.html",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

# --- 區域分類字典 ---
region_map = {
    "北部": ["F010", "F022", "F023", "F011", "F012", "F013", "F001"],
    "中部": ["F014", "F019", "F018", "F020", "F021", "F002", "F016", "F004", "F003"],
    "南部": ["F015", "F017", "F024", "F025", "F026", "F007", "F009", "F008", "F005", "F006"]
}

# --- 全台觀星地點清單 ---
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

def scrape_weekly_table(pid, location_name):
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/Week/{pid}_Week_PC.html"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return []
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        thead = soup.find("thead")
        if not thead: return []
        
        dates = []
        date_rows = thead.find_all("tr")
        if not date_rows: return []
        
        date_row = date_rows[0].find_all("th")
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
            if i >= len(dates): break
            item = {"location": location_name, "pid": pid, "date": dates[i], "時間": "白天" if i % 2 == 0 else "晚上"}
            for k, v in parsed_data.items(): 
                if k == "時間": continue
                item[k] = v[i] if i < len(v) else "未知"
            results.append(item)
        return results
    except Exception as e:
        print(f"❌ 爬取錯誤 ({location_name}): {e}")
        return []

def update_weekly_csv():
    file_name = "all_taiwan_star_forecast.csv"
    print(f"🚀 開始更新每週預報資料 (共 {len(all_locations)} 處)...")
    final_data = []
    for pid, name in all_locations.items():
        data = scrape_weekly_table(pid, name)
        if data: final_data.extend(data)
        time.sleep(0.1)
    
    if final_data:
        new_df = pd.DataFrame(final_data)
        final_df = new_df 
        final_df.to_csv(file_name, index=False, encoding="utf-8-sig")
        print(f"✅ CSV 更新完成！目前共有 {len(final_df)} 筆數據。")

def get_weekly_star_info(user_input):
    file_name = "all_taiwan_star_forecast.csv"
    try:
        if not os.path.exists(file_name): return "⚠️ 找不到資料檔，請聯繫管理員更新資料庫。"
        df = pd.read_csv(file_name, encoding="utf-8-sig")
        target_df = df[(df['location'].str.contains(user_input, na=False)) & (df['時間'] == "晚上")].copy()
        
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
            weather = str(item.get('天氣狀況', '未知'))
            score = 1
            eval_msg = ""
            
            if "晴" in weather:
                score = 3
                try:
                    t_str = str(item.get('最高溫', 0)).replace("..", "")
                    t_high = int(float(t_str)) if t_str.isdigit() else 20
                    if t_high > 15: score += 1
                    if 20 <= t_high <= 25: score += 1
                except: pass
                try:
                    wind_str = str(item.get('蒲福風級', '0'))
                    wind_matches = re.findall(r'\d+', wind_str)
                    if wind_matches and int(wind_matches[-1]) >= 5: score -= 1
                except: pass
                try:
                    fl_str = str(item.get('體感最低溫', 20)).replace("..", "")
                    fl = int(float(fl_str)) if fl_str.replace('.', '', 1).isdigit() else 20
                    if fl < 15: eval_msg = "天氣寒冷，建議多穿保暖衣物！"
                    elif 15 <= fl < 20: eval_msg = "天氣稍涼，建議穿件薄外套！"
                    elif 20 <= fl <= 25: eval_msg = "天氣舒適，絕佳觀星日！"
                    else: eval_msg = "適合觀星的溫熱夜晚！"
                except: eval_msg = "請注意現場天氣變化。"

            elif "多雲" in weather:
                score = 2
                eval_msg = "雲量較多，可碰碰運氣。"
            else:
                score = 1
                eval_msg = "今晚不適合觀星。"

            stars = "⭐" * max(1, min(5, score))
            res = [
                f"📅 {item['date']} ({item['時間']})",
                f"天氣：{weather}",
                f"氣溫：{item.get('最低溫', '?')}~{item.get('最高溫', '?')}°C",
                f"體感：{item.get('體感最低溫', '?')}~{item.get('體感最高溫', '?')}°C",
                f"降雨：{item.get('降雨機率', '未知')}",
                f"觀星推薦指數：{stars}",
                f"📝 評估：{eval_msg}"
            ]
            all_blocks.append("\n".join(res))
            
        header = f"🌌 【{user_input}】未來一週觀星指南\n\n"
        tail = "\n\n----------------\n🔔 溫馨提醒：山區天氣多變，出發前請再次確認！\n\n"
        return header + "\n\n----------------\n".join(all_blocks) + tail
    except Exception as e: return f"❌ 錯誤：{str(e)}"


# ==========================================
# 功能 B：臨時興起 (72hr 即時爬蟲 - 修復版)
# ==========================================

def format_time_ranges(time_list):
    if not time_list: return ""
    hours = []
    for t in time_list:
        try:
            h_str = t.split(':')[0]
            hours.append(int(h_str))
        except: continue
        
    if not hours: return ""

    has_evening = any(h >= 18 for h in hours)
    processed = [h + 24 if (h <= 5 and has_evening) else h for h in hours]
    processed.sort()
    
    ranges = []
    if not processed: return ""

    start_h = prev_h = processed[0]
    for i in range(1, len(processed)):
        curr = processed[i]
        if curr == prev_h + 1:
            prev_h = curr
        else:
            ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
            start_h = prev_h = curr
    ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
    return "、".join(ranges)

def get_impromptu_star_info(pid, location_name):
    # 加上亂數參數避免快取
    url = f"https://www.cwa.gov.tw/V8/C/L/StarView/MOD/3hr/{pid}_3hr_PC.html?t={int(time.time())}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        if resp.status_code != 200:
            return f"❌ 無法取得資料 (狀態碼: {resp.status_code})，請稍後再試。"

        raw_html = f"<table>{resp.text}</table>" if "<table" not in resp.text else resp.text
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # --- 1. 抓取日期對照表 ---
        date_map = {}
        for th in soup.find_all("th"):
            th_id = th.get("id")
            if th_id and "PC3_D" in th_id and "H" not in th_id and th_id != "PC3_D":
                key = th_id.split("_")[-1] 
                date_map[key] = th.get_text(strip=True)[:5]

        # --- 2. 抓取時間列 (核心防呆修正) ---
        time_row = soup.find("tr", class_="time")
        
        # 🔥 如果找不到時間列，代表網站結構改變或被擋，直接回傳提示，不要當機
        if not time_row:
            return f"⚠️ 暫時無法讀取 {location_name} 的即時資料（來源網站無回應），請改用「未來一週」功能。"

        time_full_labels = {}
        time_ids = []
        
        for th in time_row.find_all("th"):
            tid = th.get('id')
            if not tid: continue
            matched_date_key = next((dk for dk in date_map if dk in tid), None)
            if matched_date_key:
                time_str = th.get_text(strip=True)
                time_full_labels[tid] = f"{date_map[matched_date_key]} {time_str}"
                time_ids.append(tid)

        # --- 3. 抓取天氣數據 ---
        master_data = {tid: {} for tid in time_ids}
        for row in soup.find_all("tr"):
            th = row.find("th")
            if not th: continue
            title = th.get_text(strip=True)
            if "時間" in title: continue

            for td in row.find_all("td"):
                h_attr = td.get('headers', "")
                val = "未知"
                img = td.find("img")
                span = td.find("span", class_="tem-C")
                if img: val = img.get('title')
                elif span: val = span.get_text(strip=True)
                else: val = td.get_text(strip=True)

                for tid in time_ids:
                    if tid in h_attr:
                        master_data[tid][title] = val

        # --- 4. 篩選今晚 ---
        night_status = []
        check_ids = time_ids[:24] if len(time_ids) > 24 else time_ids
        for tid in check_ids:
            if tid not in time_full_labels: continue
            full_time_str = time_full_labels[tid] 
            try:
                t_part = full_time_str.split(" ")[1]
                hour = int(t_part.split(":")[0])
                if hour >= 18 or hour <= 5:
                    w = master_data[tid].get("天氣狀況", "未知")
                    night_status.append((t_part, w))
            except: continue

        # --- 5. 產生建議 ---
        perfect_times = [t for t, w in night_status if "晴" in w]
        cloudy_times = [t for t, w in night_status if "多雲" in w and "晴" not in w]
        
        if perfect_times:
            return f"🔭 【{location_name}】觀星建議：😊 \n太棒了！今晚最適合觀星的時段為：{format_time_ranges(perfect_times)}"
        elif cloudy_times:
            return f"🔭 【{location_name}】觀星建議：😐 \n今晚雲量較多，若要碰運氣可選這些時段：{format_time_ranges(cloudy_times)}"
        elif not night_status:
            return f"🔭 【{location_name}】\n目前氣象局尚未更新今晚的詳細資料，請稍晚再試。"
        else:
            return f"🔭 【{location_name}】觀星建議：😭 \n今晚天氣不佳（陰天或雨），不建議前往觀星。"

    except Exception as e:
        # 回傳錯誤訊息給使用者，而不是讓程式崩潰
        return f"❌ 抱歉，查詢 {location_name} 時發生資料讀取錯誤，請稍後再試。"

# ==========================================
# 主程式測試區
# ==========================================

if __name__ == "__main__":
    # 1. 第一次執行建議跑一次更新
    # update_weekly_csv() 
    
    print("\n--------- 模擬 LINE Bot 使用者操作 ---------")
    
    # 測試 A：未來一週 (測試星星邏輯)
    print("🔹 用戶點選：未來一週觀星指南 -> 選擇：陽明山小油坑")
    print(get_weekly_star_info("小油坑"))
    
    print("\n-------------------------------------------")
    
    # 測試 B：臨時出發 (測試時段合併與文字邏輯)
    # 建議找一個現在是晚上的時間測試，或者找鹿林天文台這種容易有晴天的
    print("🔹 用戶點選：臨時興起去觀星 -> 選擇：鹿林天文台")
    print(get_impromptu_star_info("F017", "鹿林天文台"))