import requests
import json
import sys

# 修正 Windows 輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

# 🔑 請填入你的 API Key
API_KEY = "CWA-ECEF9B5A-57C0-43F8-80D6-C08C9D67B257"

# 我們要檢查的目標 ID (你原本的清單)
MY_TARGET_IDS = [
    "F001", "F002", "F003", "F004", "F005", "F006", "F007", "F008", 
    "F009", "F010", "F011", "F012", "F013", "F014", "F015", "F016", 
    "F017", "F018", "F019", "F020", "F021", "F022", "F023", "F024", 
    "F025", "F026"
]

def check_file_api():
    # 🔥 關鍵修正：使用 fileapi 路徑，而不是 datastore
    data_id = "F-B0053-071" # 觀星三天3小時預報
    url = f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/{data_id}"
    
    params = {
        "Authorization": API_KEY,
        "format": "JSON"
    }
    
    print(f"🚀 正在嘗試下載檔案: {data_id} ...")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ 下載失敗 (Status: {response.status_code})")
            print(f"回傳訊息: {response.text}")
            return

        print("✅ 下載成功！正在解析資料...")
        
        # 解析 JSON (檔案類的結構通常是 cwaopendata -> dataset -> locations)
        data = response.json()
        
        # 嘗試找出地點列表 (結構可能因檔案而異，這邊做個防呆)
        try:
            locations = data['cwaopendata']['Dataset']['Locations']['Location']
        except KeyError:
            # 有時候結構會少一層，試試看另一種可能
            locations = data['cwaopendata']['dataset']['locations']['location']

        # 建立 API 裡有的 ID 清單
        available_map = {}
        for loc in locations:
            name = loc['LocationName']
            
            # 尋找 ID 參數
            pid = "未知"
            # 檔案 API 的參數通常藏在 ParameterSet 裡面
            if 'ParameterSet' in loc and 'Parameter' in loc['ParameterSet']:
                params_list = loc['ParameterSet']['Parameter']
                # 有時候是 list, 有時候是 dict
                if isinstance(params_list, list):
                    for p in params_list:
                        if p['ParameterName'] == 'id':
                            pid = p['ParameterValue']
                            break
                elif isinstance(params_list, dict):
                    if params_list['ParameterName'] == 'id':
                        pid = params_list['ParameterValue']
            
            if pid != "未知":
                available_map[pid] = name

        print(f"\n📋 這份資料包含 {len(available_map)} 個地點。")
        print("-" * 40)
        
        # 開始比對
        missing_count = 0
        print("🔍 比對結果：")
        
        for target in MY_TARGET_IDS:
            if target in available_map:
                print(f"  ✅ {target} 存在 ({available_map[target]})")
            else:
                print(f"  ❌ {target} 缺失！")
                missing_count += 1
        
        print("-" * 40)
        if missing_count == 0:
            print("🏆 完美！所有地點都支援！這是最棒的 API！")
        else:
            print(f"⚠️ 有 {missing_count} 個地點找不到 (可能需要用鄉鎮預報補齊)。")

        # 順便印出第一筆資料的欄位，確認有沒有「雲量」
        print("\n📊 檢查資料欄位 (確認是否有雲量):")
        if locations:
            first_elem = locations[0]['WeatherElement']
            for el in first_elem:
                print(f"  - {el['ElementName']}")

    except Exception as e:
        print(f"💥 發生錯誤: {e}")

if __name__ == "__main__":
    check_file_api()