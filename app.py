import os
from dotenv import load_dotenv  # 匯入讀取工具

load_dotenv()  # 這一行會去讀取 .env 檔案裡的內容

# 原本你可能寫死密碼，現在改成這樣：
# 意思是：「去系統環境裡找一個叫做 CHANNEL_SECRET 的東西給我」
channel_secret = os.getenv('CHANNEL_SECRET')
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')