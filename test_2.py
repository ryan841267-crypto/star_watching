import requests
import re
import ast
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.cwa.gov.tw/V8/C/L/StarView/StarView.html"
}

def debug_gt_structure():
    url = "https://www.cwa.gov.tw/Data/js/GT/TableData_GT_R_StarView.js"
    print(f"🔍 正在檢查變數結構: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        clean_text = response.text.replace('null', 'None').replace('true', 'True').replace('false', 'False')
        
        # 抓取 GT 變數
        pattern = r"var\s+GT\s*=\s*(\{.*?\})\s*;"
        match = re.search(pattern, clean_text, re.DOTALL)
        
        if match:
            content = match.group(1)
            try:
                data = ast.literal_eval(content)
                print("\n✅ GT 變數解析成功！")
                print(f"📊 資料型態: {type(data)}")
                
                if isinstance(data, dict):
                    # 印出所有的 Keys 看看是不是 PID
                    keys = list(data.keys())
                    print(f"🔑 所有 Keys (前 5 個): {keys[:5]}")
                    
                    if keys:
                        first_key = keys[0]
                        first_value = data[first_key]
                        print(f"\n📄 第一筆資料內容 ({first_key}):")
                        print(json.dumps(first_value, ensure_ascii=False, indent=4))
                        
                        # 幫你自動檢查中文名稱在哪裡
                        if isinstance(first_value, dict):
                            print("\n🕵️‍♂️ 自動偵測中文欄位:")
                            for k, v in first_value.items():
                                print(f"   - Key: ['{k}'] -> Value: {v}")
                else:
                    print("⚠️ GT 不是字典，而是:", data)
                    
            except Exception as e:
                print(f"❌ 解析內容時發生錯誤: {e}")
                print("原始字串開頭:", content[:100])
        else:
            print("❌ 找不到 var GT = ...")

    except Exception as e:
        print(f"❌ 連線錯誤: {e}")

if __name__ == "__main__":
    debug_gt_structure()