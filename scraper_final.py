import pandas as pd
import time
import sys
import os
import re
from datetime import datetime, timedelta, timezone
from curl_cffi import requests as cffi_requests # ✨ 關鍵：使用偽裝瀏覽器請求

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# 🔑 設定區
# ==========================================
CWA_API_KEY = os.getenv("CWA_API_KEY") 

# ==========================================
# 📍 地點清單 (對應 API ID)
# ==========================================
all_locations = {
    "F001": "太平山森林遊樂區", "F002": "小風口停車場", "F003": "鳶峰停車場",
    "F004": "台大梅峰實驗農場", "F005": "墾丁貓鼻頭", "F006": "墾丁龍磐公園",
    "F007": "高雄梅山青年活動中心", "F008": "藤枝森林遊樂區", "F009": "高雄都會公園",
    "F010": "基隆大武崙砲台停車場", "F011": "五分山", "F012": "石碇雲海國小",
    "F013": "烏來風景特定區", "F014": "觀霧森林遊樂區", "F015": "阿里山遊樂區",
    "F016": "新中橫塔塔加停車場", "F017": "鹿林天文台", "F018": "武陵農場",
    "F019": "大雪山國家森林遊樂區", "F020": "福壽山農場", "F021": "臺中都會公園",
    "F022": "陽明山國家公園小油坑停車場", "F023": "陽明山國家公園擎天崗",
    "F024": "七股海堤", "F025": "南瀛天文教育園區", "F026": "臺南都會公園"
}

# ==========================================
# 🛠️ 核心函式：使用 curl_cffi 下載 API (抗封鎖版)
# ==========================================
def fetch_file_api_data(data_id):
    """
    使用 curl_cffi 模擬 Chrome 瀏覽器下載氣象署 API，
    徹底解決 SSL 憑證錯誤 (Missing Subject Key Identifier) 與 WAF 阻擋問題。
    """
    url = f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/{data_id}"
    params = {"Authorization": CWA_API_KEY, "format": "JSON"}
    
    try:
        # ✨ 魔法在這裡：impersonate="chrome110"
        # 這會讓你的程式碼在網路上看起來像是一個真實的 Chrome 瀏覽器
        response = cffi_requests.get(
            url, 
            params=params, 
            impersonate="chrome110", 
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ API 下載失敗 (Status {response.status_code}): {url}")
            return None
    except Exception as e:
        print(f"❌ API 連線嚴重錯誤: {e}")
        return None

def find_location_data(json_data, target_pid):
    try:
        root = json_data.get('cwaopendata', {})
        dataset = root.get('Dataset', root.get('dataset', {}))
        locations_node = dataset.get('Locations', dataset.get('locations', {}))
        location_list = locations_node.get('Location', locations_node.get('location', []))

        for loc in location_list:
            current_pid = None
            param_set = loc.get('ParameterSet', loc.get('parameterSet', {}))
            params = param_set.get('Parameter', param_set.get('parameter', []))
            
            p_list = params if isinstance(params, list) else [params]
            for p in p_list:
                if p.get('ParameterName') == 'id':
                    current_pid = p.get('ParameterValue')
                    break
            
            if current_pid == target_pid:
                return loc
        return None
    except: return None

# ==========================================
# 💾 CSV 更新功能 (保留你的歷史資料需求)
# ==========================================
def update_weekly_csv():
    # 抓取「未來一週 (F-B0053-069)」資料
    data = fetch_file_api_data("F-B0053-069")
    if not data:
        print("❌ 無法取得一週預報資料，跳過 CSV 更新。")
        return

    csv_data = []
    print(f"🚀 正在更新 CSV 資料庫...")

    for pid, name in all_locations.items():
        loc = find_location_data(data, pid)
        if not loc: continue
        
        raw_elements = loc.get('WeatherElement', [])
        elements = {item.get('ElementName'): item.get('Time', []) for item in raw_elements}

        # F-B0053-069 每 12 小時一筆 (早/晚)
        ref_time_list = elements.get('天氣現象', [])
        
        for i, time_item in enumerate(ref_time_list):
            start_str = time_item.get('StartTime') 
            if not start_str: continue
            
            dt = datetime.fromisoformat(start_str)
            date_display = dt.strftime("%m/%d")
            time_label = "晚上" if dt.hour == 18 else "白天"

            try:
                wx = time_item['ElementValue']['Weather']
                
                # 輔助函式：安全取得數值
                def get_val(key, idx):
                    lst = elements.get(key, [])
                    if idx < len(lst):
                        val_dict = lst[idx]['ElementValue']
                        return list(val_dict.values())[0] # 取第一個值最保險
                    return "-"

                min_t = get_val('最低溫度', i)
                max_t = get_val('最高溫度', i)
                min_at = get_val('最低體感溫度', i)
                max_at = get_val('最高體感溫度', i)
                pop = get_val('12小時降雨機率', i)
                pop = f"{pop}%" if pop != " " else "0%"
                wind = get_val('蒲福風級', i)

                row = {
                    "location": name, "pid": pid, "date": date_display, "時間": time_label,
                    "天氣狀況": wx, "最低溫": min_t, "最高溫": max_t,
                    "體感最低溫": min_at, "體感最高溫": max_at,
                    "降雨機率": pop, "蒲福風級": wind
                }
                csv_data.append(row)
            except: continue

    if csv_data:
        file_name = "all_taiwan_star_forecast.csv"
        df = pd.DataFrame(csv_data)
        df.to_csv(file_name, index=False, encoding="utf-8-sig")
        print(f"✅ CSV 更新成功！已寫入 {len(df)} 筆資料。")
    else:
        print("⚠️ 雖然抓到 API 但沒有解析出有效資料。")

# ==========================================
# 🔭 功能 A：今晚觀星 (使用 F-B0053-071)
# ==========================================
def format_time_ranges(time_list):
    if not time_list: return ""
    hours = []
    for t in time_list:
        try: hours.append(int(t.split(':')[0]))
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
        if curr == prev_h + 1: prev_h = curr
        else:
            ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
            start_h = prev_h = curr
    ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
    return "、".join(ranges)

def get_impromptu_star_info(pid, location_name):
    # 下載 3hr 資料 (抗封鎖)
    data = fetch_file_api_data("F-B0053-071") 
    if not data: return "⚠️ 氣象署連線忙碌中，請稍後再試。"
    
    loc_data = find_location_data(data, pid)
    if not loc_data: return f"❌ 無資料: {location_name}"

    try:
        raw_elements = loc_data.get('WeatherElement', [])
        elements = {item.get('ElementName'): item.get('Time', []) for item in raw_elements}

        night_status = [] # (時間, 天氣)
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        
        weather_list = elements.get('天氣現象', [])
        for i, item in enumerate(weather_list):
            t_str = item.get('DataTime') or item.get('StartTime')
            if not t_str: continue
            dt = datetime.fromisoformat(t_str)

            # 篩選未來24h內的晚上
            if dt > now and (dt.hour >= 18 or dt.hour <= 5):
                if (dt - now).total_seconds() > 86400: continue
                
                wx = item['ElementValue']['Weather']
                night_status.append((dt.strftime('%H:%M'), wx))

        # 評分與建議
        perfect_times = [t for t, w in night_status if "晴" in w]
        cloudy_times = [t for t, w in night_status if "多雲" in w and "晴" not in w]

        if perfect_times:
            return f"🔭 【{location_name}】觀星建議：😊 \n太棒了！今晚最適合觀星的時段為：{format_time_ranges(perfect_times)}"
        elif cloudy_times:
            return f"🔭 【{location_name}】觀星建議：😐 \n今晚雲量較多，若要碰運氣可選這些時段：{format_time_ranges(cloudy_times)}"
        elif not night_status:
            return f"🔭 【{location_name}】\n目前氣象署資料更新中，請稍晚再試。"
        else:
            return f"🔭 【{location_name}】觀星建議：😭 \n今晚天氣不佳（陰天或雨），不建議前往觀星。"

    except Exception as e: return f"❌ 解析錯誤: {e}"

# ==========================================
# 📅 功能 B：未來一週 (讀取 CSV)
# ==========================================
def get_weekly_star_info(location_name):
    file_name = "all_taiwan_star_forecast.csv"
    
    # 檔案不存在時自動抓取 (修復 Render 重啟後資料消失問題)
    if not os.path.exists(file_name):
        update_weekly_csv()
    
    try:
        if not os.path.exists(file_name): return "⚠️ 資料庫暫時無法讀取，請稍後再試。"
        
        df = pd.read_csv(file_name, encoding="utf-8-sig")
        target_df = df[(df['location'].str.contains(location_name, na=False)) & (df['時間'] == "晚上")].copy()
        
        if target_df.empty: return f"找不到「{location_name}」的資料。"

        today_str = datetime.now().strftime("%m/%d")
        
        data_list = target_df.head(7).to_dict('records')
        blocks = []
        for item in data_list:
            wx = str(item.get('天氣狀況', ''))
            
            # --- 你的評分邏輯 ---
            score = 1
            eval_msg = ""
            
            if "晴" in wx:
                score = 3
                try:
                    fl = float(str(item.get('體感最低溫', '20')).replace("..", ""))
                    if fl > 15: score += 1
                    if 20 <= fl <= 25: score += 1
                    
                    if fl < 15: eval_msg = "天氣寒冷，建議多穿保暖衣物！"
                    elif 15 <= fl < 20: eval_msg = "天氣稍涼，建議穿件薄外套！"
                    else: eval_msg = "適合觀星的溫熱夜晚！"
                except: eval_msg = "請注意氣溫變化。"
                
                try:
                    ws = item.get('蒲福風級', '0')
                    wm = re.findall(r'\d+', str(ws))
                    if wm and int(wm[-1]) >= 5: score -= 1
                except: pass

            elif "多雲" in wx:
                score = 2
                eval_msg = "雲量較多，可碰運氣。"
            else:
                score = 1
                eval_msg = "今晚不適合觀星。"

            score = max(1, min(5, score))
            stars = "⭐" * score
            
            res = [
                f"📅 {item['date']} (晚)",
                f"天氣: {wx}",
                f"氣溫: {item['最低溫']}~{item['最高溫']}°C",
                f"降雨: {item['降雨機率']}",
                f"指數: {stars}",
                f"📝 {eval_msg}"
            ]
            blocks.append("\n".join(res))
            
        return f"🌌 【{location_name}】未來一週預報\n----------------------\n" + "\n\n".join(blocks)

    except Exception as e:
        return f"❌ 讀取資料失敗，正在重新抓取...({e})"

if __name__ == "__main__":
    if not CWA_API_KEY:
        print("❌ 請先設定 CWA_API_KEY 環境變數！")
    else:
        # 測試一下
        print("測試更新 CSV...")
        update_weekly_csv()
        print("測試讀取...")
        print(get_weekly_star_info("鹿林天文台"))