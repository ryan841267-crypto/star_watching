import pandas as pd
import sys
import os
import re
import requests # [新增] 用於呼叫 Google Maps API
from datetime import datetime, timedelta, timezone
from curl_cffi import requests as cffi_requests # ✨ 關鍵：使用偽裝瀏覽器請求
from dotenv import load_dotenv # [新增] 讓這支程式也能讀到 .env

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# 🔑 設定區
# ==========================================
# [新增] 載入環境變數 (解決你剛剛報錯的問題)
load_dotenv()

CWA_API_KEY = os.getenv("CWA_API_KEY") 
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY") # [新增] Google API Key

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

# [新增] 景點座標資料庫 (API 計算必須要有精確經緯度)
# 格式: "PID": (緯度, 經度)
LOCATION_COORDS = {
    "F001": (24.49305556, 121.536666), # 太平山
    "F002": (24.16222222, 121.288055), # 小風口
    "F003": (24.11805556, 121.2372222), # 鳶峰
    "F004": (24.0880555, 121.1744444), # 台大梅峰
    "F005": (21.92166667, 120.7372222), # 貓鼻頭
    "F006": (21.92027778, 120.8527778), # 龍磐公園
    "F007": (23.26527778, 120.8252778), # 梅山青年活動中心
    "F008": (23.0672222, 120.7555556), # 藤枝
    "F009": (22.73305556, 120.3069444), # 高雄都會公園
    "F010": (25.15777778, 121.7097222), # 大武崙砲台
    "F011": (25.07047785, 121.781691), # 五分山
    "F012": (24.95305556, 121.6366667), # 石碇雲海國小
    "F013": (24.84888889, 121.551666), # 烏來
    "F014": (24.50666667, 121.1141667), # 觀霧
    "F015": (23.51305556, 120.8083333), # 阿里山
    "F016": (23.48722222, 120.889166), # 塔塔加
    "F017": (23.46861111, 120.8736111), # 鹿林天文台
    "F018": (24.35277778, 121.31), # 武陵農場
    "F019": (24.27916667, 121.0258333), # 大雪山
    "F020": (24.24472222, 121.2452778), # 福壽山
    "F021": (24.20666667, 120.5972222), # 台中都會公園
    "F022": (25.1765691, 121.5488301), # 小油坑
    "F023": (25.16666667, 121.5741667), # 擎天崗
    "F024": (23.10895896, 120.0596368), # 七股海堤
    "F025": (23.11916667, 120.3908333), # 南瀛天文館
    "F026": (22.93555556, 120.2252778)  # 台南都會公園
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
    params = {"Authorization": CWA_API_KEY, "format": "JSON"} # 用我的憑證下載jsn檔
    
    try:
        # ✨ 魔法在這裡：impersonate="chrome110"
        # Google Chrome 大約每個月都會更新一次版本號（例如 Chrome 108, 109, 110... 直到現在的 120+）。
        # chrome110 是 curl_cffi 函式庫中一個非常穩定且具備現代安全特徵（如 HTTP/2）的預設偽裝目標。
        response = cffi_requests.get(
            url, 
            params=params, # 把參數自動加在url(網址)後面
            impersonate="chrome110", 
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            # 成功連線但沒拿到資料(被封鎖或是查不到)
            print(f"❌ API 下載失敗 (Status {response.status_code}): {url}")
            return None
    except Exception as e:
        # 連線失敗
        print(f"❌ API 連線嚴重錯誤: {e}")
        return None

def find_location_data(json_data, target_pid):
    try:
        root = json_data.get('cwaopendata', {})
        dataset = root.get('Dataset', root.get('dataset', {})) 
        locations_node = dataset.get('Locations', dataset.get('locations', {}))
        location_list = locations_node.get('Location', locations_node.get('location', [])) 
        # get包著get:先執行前面，無資料再執行後面，例如先找大小D，再找小寫d，如果都沒有就回傳自訂的空的預設型態(字典或串列)。
        # 最後找到包含不同地點(字典型態)的資訊並包成串列。

        for loc in location_list:
            current_pid = None
            param_set = loc.get('ParameterSet', loc.get('parameterSet', {}))
            params = param_set.get('Parameter', param_set.get('parameter', []))
            
            # 檢查 params 是不是清單。如果是，就直接用；
            # 如果是字典或其他，就把它包進中括號 [] 裡。這樣後面的 for p in p_list 才能統一運作。
            p_list = params if isinstance(params, list) else [params]
            for p in p_list:
                if p.get('ParameterName') == 'id':
                    current_pid = p.get('ParameterValue')
                    break
            
            # target_pid是從all_locations.items()函式跳轉過來的。
            # all_locations.items()執行迴圈，再呼叫find_location_data()。
            if current_pid == target_pid:
                return loc
        return None
    except: return None

# [新增] Google Maps Distance Matrix API 呼叫函式
# [修改] 將原本的 get_real_walking_info 改名並升級
def get_route_info(origin_lat, origin_lng, dest_lat, dest_lng, mode="driving"):
    """
    mode 參數支援: 
    - driving (開車)
    - walking (走路)
    - bicycling (自行車/騎行)
    - transit (大眾運輸 - 需特定城市支援)
    """
    if not GOOGLE_MAPS_KEY:
        return None, None
        
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{dest_lat},{dest_lng}",
        "mode": mode,  # 這裡變成變數了
        "language": "zh-TW",
        "key": GOOGLE_MAPS_KEY
    }
    try:
        res = requests.get(url, params=params).json()
        if res['status'] == 'OK':
            element = res['rows'][0]['elements'][0]
            if element['status'] == 'OK':
                # 回傳: (距離, 時間)
                return element['distance']['text'], element['duration']['text']
    except Exception as e:
        print(f"API Error ({mode}): {e}")
    return None, None

# ==========================================
# 💾 CSV 更新功能 (雙檔策略: Bot用 / 歷史用)
# ==========================================
def update_weekly_csv():
    # 抓取「未來一週 (F-B0053-069)」資料
    data = fetch_file_api_data("F-B0053-069")
    if not data:
        print("❌ 無法取得一週預報資料，跳過 CSV 更新。")
        return

    csv_data = [] # 抓取完成並需要儲存的資料
    print(f"🚀 正在更新 CSV 資料庫...")

    for pid, name in all_locations.items():
        loc = find_location_data(data, pid)
        if not loc: continue
        
        raw_elements = loc.get('WeatherElement', [])
        elements = {item.get('ElementName'): item.get('Time', []) for item in raw_elements}

        # F-B0053-069 每 12 小時一筆 (早/晚)
        ref_time_list = elements.get('天氣現象', [])
        
        # 用 enumerate 處理「多個並列清單」的同步問題。
        # 當我們用 enumerate 跑「天氣現象」清單時，我們拿到了編號 i。
        # 這時我們就可以用同一個編號 i 去「最低溫度」清單裡抓出對應的溫度。
        for i, time_item in enumerate(ref_time_list):
            start_str = time_item.get('StartTime') 
            if not start_str: continue
            
            # 把天氣現象的開始時間轉換成"01/06"格式
            # 先建立實例屬性，再透過方法轉成新的格式
            # 一週日夜資料是以6到18時做切割
            dt = datetime.fromisoformat(start_str)
            date_display = dt.strftime("%m/%d")
            time_label = "晚上" if dt.hour == 18 else "白天"

            try:
                # time_item現在是一個巢狀字典，取出後，wx是天氣狀況
                wx = time_item['ElementValue']['Weather']
                
                # 輔助函式：安全取得數值
                def get_val(key, idx):
                    # 從 elements 字典（裡面存了所有天氣元素）中，
                    # 根據 key（例如：'最低溫度'）把那一長串的時間清單拿出來。
                    lst = elements.get(key, [])
                    # 「邊界檢查」。萬一「天氣現象」有 7 筆預報，但「降雨機率」只有 5 筆，
                    # 如果不檢查，程式跑到第 6 筆時就會因為找不到資料而直接當機。
                    # 解法：val_dict.values() 會把裡面所有的「值」都拿出來（不看 Key），然後轉成 list 拿第一個 [0]。
                    # 這樣不管是天氣還是溫度，都能正確抓到那個「數值」。
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

    # ==========================================
    # 👇 修改區：資料分流 (Bot用 vs 歷史用)
    # ==========================================
    if csv_data:
        # 1. 準備當下的新資料
        current_df = pd.DataFrame(csv_data)
        
        # -------------------------------------------------------
        # 📂 檔案 A：Bot 專用 (每次覆蓋，只留最新 7 天，速度快)
        # -------------------------------------------------------
        bot_file = "all_taiwan_star_forecast.csv"
        current_df.to_csv(bot_file, index=False, encoding="utf-8-sig")
        print(f"✅ Bot 資料庫已更新 (覆蓋模式): 共 {len(current_df)} 筆")

        # -------------------------------------------------------
        # 🏛️ 檔案 B：歷史倉庫 (累積模式，保留過去所有資料)
        # -------------------------------------------------------
        history_file = "history_repository.csv"
        
        if os.path.exists(history_file):
            try:
                old_df = pd.read_csv(history_file, encoding="utf-8-sig")
                # 合併舊資料 + 新資料
                history_df = pd.concat([old_df, current_df], ignore_index=True)
                # 去除重複：如果「地點+時間」一樣，保留最新的預報 (keep='last')
                history_df.drop_duplicates(subset=['location', 'pid', 'date', '時間'], keep='last', inplace=True)
            except:
                history_df = current_df # 讀取失敗就直接用新的
        else:
            history_df = current_df # 沒檔案就直接創新的

        # [新增] 排序功能：依照 ID -> 日期 -> 時間 排列，讓歷史檔整齊
        if not history_df.empty:
            history_df.sort_values(by=['pid', 'date', '時間'], inplace=True)

        history_df.to_csv(history_file, index=False, encoding="utf-8-sig")
        print(f"📚 歷史資料庫已備份 (累積+排序): 共 {len(history_df)} 筆")

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

    # 判斷是否有「晚上（18點以後）」的資料
    has_evening = any(h >= 18 for h in hours)
    processed = [h + 24 if (h <= 5 and has_evening) else h for h in hours]
    processed.sort()
    
    ranges = []
    if not processed: return ""
    start_h = prev_h = processed[0]
    
    for i in range(1, len(processed)): # 從第2個開始
        curr = processed[i]
        if curr == prev_h + 1: prev_h = curr
        else:
            ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
            start_h = prev_h = curr
    ranges.append(f"{start_h%24:02d}:00-{(prev_h+1)%24:02d}:00")
    return "、".join(ranges)

def get_impromptu_star_info(pid, location_name):
    # 即時下載 3hr 資料
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
            # [修改 1] 同時取得開始與結束時間
            start_str = item.get('StartTime')
            end_str = item.get('EndTime')
            if not start_str or not end_str: continue
            
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            wx = item['ElementValue']['Weather']

            # [修改 2] 將 3 小時的時間區段，「展開」成每個小時
            # 例如 18:00~21:00 -> 產生 18:00, 19:00, 20:00 三筆資料
            current_pointer = start_dt
            while current_pointer < end_dt:
                # 判斷是否為晚上 (18~05) 且是未來時間
                if current_pointer > now and (current_pointer.hour >= 18 or current_pointer.hour <= 5):
                    # 檢查是否超過 24 小時 (避免顯示太多天後的資料)
                    if (current_pointer - now).total_seconds() <= 86400:
                        night_status.append((current_pointer.strftime('%H:%M'), wx))
                
                # 往後推一小時
                current_pointer += timedelta(hours=1)

        # 1. 最優先判斷：是否有壞天氣 (陰天或雨)
        # 只要這段時間內出現任何 "陰" 或 "雨" 的字眼，就直接勸退
        has_bad_weather = any("陰" in w or "雨" in w for t, w in night_status)

        if has_bad_weather:
            return f"🔭 【{location_name}】觀星建議：😭 \n今晚天氣不佳，不建議前往觀星，請好好睡覺。"

        # 2. 如果沒有壞天氣，才開始找好天氣
        perfect_times = [t for t, w in night_status if "晴" in w] # 抓"晴"、"晴時多雲"、"多雲時晴"三種天氣
        cloudy_times = [t for t, w in night_status if "多雲" in w and "晴" not in w]
        
        # 去除重複並保持順序
        perfect_times = sorted(list(set(perfect_times)), key=lambda x: (int(x.split(':')[0]) + 24) if int(x.split(':')[0]) < 12 else int(x.split(':')[0]))
        cloudy_times = sorted(list(set(cloudy_times)), key=lambda x: (int(x.split(':')[0]) + 24) if int(x.split(':')[0]) < 12 else int(x.split(':')[0]))

        if perfect_times:
            return f"🔭 【{location_name}】觀星建議：😊 \n太棒了！今晚最適合觀星的時段為：{format_time_ranges(perfect_times)}"
        elif cloudy_times:
            return f"🔭 【{location_name}】觀星建議：😐 \n今晚雲量較多，可碰運氣的時段為：{format_time_ranges(cloudy_times)}"
        elif not night_status:
            return f"🔭 【{location_name}】\n目前中央氣象署資料更新中，請稍晚再試。"
        else:
            # 這裡理論上跑不到了，因為壞天氣都被第一個 if 抓走了，但留著當保險
            return f"🔭 【{location_name}】觀星建議：😭 \n今晚天氣不佳，不建議前往觀星，請好好睡覺。"

    except Exception as e: return f"❌ 解析錯誤: {e}"

# ==========================================
# 📅 功能 B：未來一週 (Bot 讀取專用)
# ==========================================
def get_weekly_star_info(location_name):
    file_name = "all_taiwan_star_forecast.csv"
    
    # ==========================================
    # 🕵️‍♂️ 智慧檢查機制 (開始)
    # ==========================================
    # 1. 取得「台灣時間」今天的日期字串 (格式必須跟 CSV 裡的 "01/27" 一模一樣)
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    today_str = now_tw.strftime("%m/%d")
    
    need_update = False

    # 2. 第一關：檢查檔案在不在
    if not os.path.exists(file_name):
        print(f"⚠️ 找不到 {file_name}，準備下載...")
        need_update = True
    else:
        # 3. 第二關：檢查內容有沒有過期
        try:
            # 為了省資源，我們只讀取 'date' 這一欄就好
            df_check = pd.read_csv(file_name, usecols=['date'], encoding="utf-8-sig")
            
            # 邏輯：如果 CSV 裡的所有日期，完全找不到「今天」，代表這份資料是舊的
            # .values 是把欄位轉成陣列，比較速度快
            if today_str not in df_check['date'].values:
                # 為了 debug 方便，印出它最新的日期是哪一天
                last_date = df_check['date'].iloc[-1] if not df_check.empty else "空檔案"
                print(f"⚠️ 資料庫過期 (檔案最新日期: {last_date}，今天是: {today_str})，強制更新...")
                need_update = True
            else:
                print("✅ 資料庫有效 (包含今日資料)，直接讀取。")
                
        except Exception as e:
            print(f"⚠️ 檔案讀取異常或格式錯誤 ({e})，保險起見強制重抓...")
            need_update = True

    # 4. 如果上面的檢查判斷需要更新，就在這裡執行爬蟲
    if need_update:
        update_weekly_csv()
    # ==========================================
    # 🕵️‍♂️ 智慧檢查機制 (結束)
    # ==========================================
    
    try:
        if not os.path.exists(file_name): return "⚠️ 資料庫暫時無法讀取，請稍後再試。"
        
        df = pd.read_csv(file_name, encoding="utf-8-sig")
        target_df = df[(df['location'].str.contains(location_name, na=False)) & (df['時間'] == "晚上")].copy()
        
        if target_df.empty: return f"找不到「{location_name}」的資料。"

        # 直接取前 7 筆 (因為檔案只有最新的，不用過濾日期)
        data_list = target_df.head(7).to_dict('records')
        blocks = []
        for item in data_list:
            wx = str(item.get('天氣狀況', ''))
            
            # --- 評分邏輯 ---
            score = 1
            eval_msg = ""

            # 1. 最優先檢查：壞天氣 (陰天或雨)
            # 只要出現這兩個字，直接判定為不適合，也不用管溫度了
            if "陰" in wx or "雨" in wx:
                score = 1
                eval_msg = "今晚不適合觀星。"

            # 2. 好天氣檢查：晴天 或 多雲
            elif "晴" in wx or "多雲" in wx:
                # --- A. 決定基礎分數與開頭語 ---
                if "晴" in wx:
                    score = 3
                    eval_msg = "今晚高機率看到星星哦！"
                else:
                    # 這裡代表只有「多雲」(沒有晴也沒有雨/陰)
                    score = 2
                    eval_msg = "今晚雲量較多，很想看星星的話可碰碰運氣。"
                
                # --- B. 溫度判斷 (晴天跟多雲都用這一套) ---
                try:
                    fl = float(str(item.get('體感最低溫', '20')).replace("..", ""))
                    
                    # 溫度加分邏輯
                    if fl > 15: score += 1
                    if 20 <= fl <= 25: score += 1
                    
                    # 溫度建議訊息 (記得加 \n 換行)
                    if fl < 15: eval_msg += "另今晚天氣寒冷，外出觀星建議多穿保暖衣物！"
                    elif 15 <= fl < 20: eval_msg += "另今晚天氣稍涼，外出觀星建議穿件薄外套！"
                    elif 20 <= fl <= 25: eval_msg += "另今晚天氣舒適，絕佳觀星日！"
                    else: eval_msg += "另今晚是適合觀星的溫熱夜晚！"
                except:
                    eval_msg += "\n(溫度資料暫缺，請注意氣溫變化)"

                # --- C. 風力扣分 (晴天跟多雲都用這一套) ---
                try:
                    ws = item.get('蒲福風級', '0')
                    wm = re.findall(r'\d+', str(ws))
                    if wm and int(wm[-1]) >= 5: score -= 1
                except: pass

            # 3. 其他未知天氣
            else:
                score = 1
                eval_msg = "今晚不適合觀星。"

            # 確保分數在 1~5 之間
            score = max(1, min(5, score))
            stars = "⭐" * score
            
            # 修正後的 f-string (補上了引號)
            res = [
                f"📅 {item['date']} (晚上)",
                f"天氣: {wx}",
                f"氣溫: {item['最低溫']}~{item['最高溫']}°C",
                f"體感: {item.get('體感最低溫', '?')}~{item.get('體感最高溫', '?')}°C",
                # f"降雨: {item['降雨機率']}",
                f"觀星推薦指數: {stars}",
                f"📝綜合評估: {eval_msg}"
            ]
            blocks.append("\n".join(res))
            
        header = f"🌌 【{location_name}】未來一週觀星指南\n"
        tail = "\n\n----------------\n🔔 溫馨提醒：當日可再確認晴朗的晚間時段哦！"
        return header + "----------------------\n" + "\n\n".join(blocks) + tail

    except Exception as e:
        return f"❌ 讀取資料失敗，正在重新抓取...({e})"

if __name__ == "__main__":
    if not CWA_API_KEY:
        print("❌ 請先設定 CWA_API_KEY 環境變數！")
    else:
        # 測試
        print("測試更新 CSV (雙檔策略)...")
        update_weekly_csv()
        print("\n測試讀取 (Bot 模式)...")
        print(get_weekly_star_info("鹿林天文台"))