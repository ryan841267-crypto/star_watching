import requests
import json
import time
import sys
import os
import re # 用來處理風速 ">= 6" 這種字串
from datetime import datetime, timedelta, timezone

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# 🔑 設定區
# ==========================================
CWA_API_KEY = os.getenv("CWA_API_KEY") # 從環境變數讀取

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
# 🛠️ 核心函式：下載並解析 API
# ==========================================
def fetch_file_api_data(data_id):
    url = f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/{data_id}"
    params = {"Authorization": CWA_API_KEY, "format": "JSON"}
    try:
        response = requests.get(url, params=params, timeout=20)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"❌ API 連線錯誤: {e}")
        return None

def find_location_data(json_data, target_pid):
    try:
        # 尋找地點資料 (相容大小寫)
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
# 功能 A：臨時興起 (保留原本的時間合併邏輯)
# ==========================================
def format_time_ranges(time_list):
    # 這是你原本的時段合併函式 (EX: 18:00, 19:00 -> 18:00-20:00)
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
        if curr == prev_h + 1: # 如果是連續的
            prev_h = curr
        else: # 中斷了，結算上一段
            ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
            start_h = prev_h = curr
    ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
    return "、".join(ranges)

def get_impromptu_star_info(pid, location_name):
    # 使用 F-B0053-071 (未來3天，每3小時)
    data = fetch_file_api_data("F-B0053-071")
    if not data: return "⚠️ 無法連線至氣象署 API，請稍後再試。"

    loc_data = find_location_data(data, pid)
    if not loc_data: return f"❌ 找不到【{location_name}】的資料。"

    try:
        # 整理資料
        raw_elements = loc_data.get('WeatherElement', [])
        elements = {item.get('ElementName'): item.get('Time', []) for item in raw_elements}

        # 準備容器，邏輯與你原本的一樣
        night_status = [] # 存 (時間, 天氣)
        
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        
        # 遍歷「天氣現象」
        wx_list = elements.get('天氣現象', [])
        for time_item in wx_list:
            time_str = time_item.get('DataTime') or time_item.get('StartTime')
            if not time_str: continue
            
            dt = datetime.fromisoformat(time_str)
            
            # 篩選條件：未來24小時 + 晚上 (18-05點)
            if dt > now and (dt.hour >= 18 or dt.hour <= 5):
                if (dt - now).total_seconds() > 86400: continue
                
                wx = time_item['ElementValue']['Weather']
                time_label = dt.strftime('%H:%M')
                night_status.append((time_label, wx))

        # --- 原本的輸出判斷邏輯 ---
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
        return f"❌ 解析錯誤: {e}"

# ==========================================
# 功能 B：未來一週 (保留原本的評分邏輯)
# ==========================================
def get_weekly_star_info(location_name):
    # 1. 反查 PID
    pid = next((k for k, v in all_locations.items() if location_name in v), None)
    if not pid: 
        # 模糊搜尋
        for k, v in all_locations.items():
            if location_name in v:
                pid = k
                break
    if not pid: return "❌ 找不到此地點資料"
    
    full_name = all_locations[pid]

    # 2. 下載 F-B0053-069 (一週預報)
    data = fetch_file_api_data("F-B0053-069")
    if not data: return "⚠️ API 連線忙碌中"

    loc_data = find_location_data(data, pid)
    if not loc_data: return "❌ 無資料"

    try:
        raw_elements = loc_data.get('WeatherElement', [])
        elements = {item.get('ElementName'): item.get('Time', []) for item in raw_elements}
        
        report_blocks = []
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

        # 遍歷「天氣現象」(每12小時一筆)
        wx_list = elements.get('天氣現象', [])
        
        for i, time_item in enumerate(wx_list):
            start_str = time_item.get('StartTime')
            if not start_str: continue
            start_dt = datetime.fromisoformat(start_str)
            
            # 只抓「晚上 (18:00開始)」且是「未來」
            if start_dt > now and start_dt.hour == 18:
                
                # --- 取得原本邏輯需要的變數 ---
                weather = time_item['ElementValue']['Weather'] # 天氣
                
                # 體感最低溫 (用來評估穿著)
                try:
                    min_at_list = elements.get('最低體感溫度', [])
                    at_val = min_at_list[i]['ElementValue']['MinApparentTemperature']
                    fl = float(at_val)
                except: fl = 20 # 預設值防止當機
                
                # 蒲福風級 (用來扣分)
                try:
                    wind_list = elements.get('蒲福風級', [])
                    wind_str = wind_list[i]['ElementValue']['BeaufortScale']
                    # 處理 ">= 6" 這種字串
                    wind_matches = re.findall(r'\d+', wind_str)
                    wind_scale = int(wind_matches[-1]) if wind_matches else 0
                except: wind_scale = 0

                # 降雨機率
                try:
                    pop_list = elements.get('12小時降雨機率', [])
                    pop = pop_list[i]['ElementValue']['ProbabilityOfPrecipitation']
                    pop_str = f"{pop}%" if pop != " " else "-"
                except: pop_str = "-"
                
                # 溫度範圍 (顯示用)
                try:
                    min_t = elements['最低溫度'][i]['ElementValue']['MinTemperature']
                    max_t = elements['最高溫度'][i]['ElementValue']['MaxTemperature']
                    temp_str = f"{min_t}~{max_t}"
                except: temp_str = "?"

                # ==============================
                # 🌟 這裡是你原本的評分邏輯 🌟
                # ==============================
                score = 1
                eval_msg = ""

                if "晴" in weather:
                    score = 3
                    # 氣溫加分
                    if fl > 15: score += 1
                    if 20 <= fl <= 25: score += 1
                    
                    # 風速扣分 (>=5級扣分)
                    if wind_scale >= 5: score -= 1
                    
                    # 評語 (原本的邏輯)
                    if fl < 15: eval_msg = "天氣寒冷，外出觀星建議多穿保暖衣物！"
                    elif 15 <= fl < 20: eval_msg = "天氣稍涼，外出觀星建議穿件薄外套！"
                    elif 20 <= fl <= 25: eval_msg = "天氣舒適，絕佳觀星日！"
                    else: eval_msg = "適合觀星的溫熱夜晚！"

                elif "多雲" in weather:
                    score = 2
                    eval_msg = "雲量較多，可碰碰運氣。"
                else:
                    score = 1
                    eval_msg = "今晚不適合觀星。"

                # 限制星星數量 1~5
                score = max(1, min(5, score))
                stars = "⭐" * score

                # 組合輸出文字
                res = [
                    f"📅 {start_dt.strftime('%m/%d')} (晚)",
                    f"天氣：{weather}",
                    f"氣溫：{temp_str}°C",
                    f"體感：{fl}°C", # 顯示一下體感，讓使用者知道為何有評語
                    f"降雨：{pop_str}",
                    f"觀星推薦指數：{stars}",
                    f"📝 評估：{eval_msg}"
                ]
                report_blocks.append("\n".join(res))

        header = f"🌌 【{full_name}】未來一週預報\n"
        return header + "----------------------\n" + "\n\n".join(report_blocks[:7])

    except Exception as e:
        return f"❌ 錯誤: {e}"

# 為了相容 app.py，留個空殼
def update_weekly_csv():
    pass

if __name__ == "__main__":
    if not CWA_API_KEY:
        print("❌ 請設定 CWA_API_KEY 環境變數")
    else:
        print(get_impromptu_star_info("F017", "鹿林天文台"))