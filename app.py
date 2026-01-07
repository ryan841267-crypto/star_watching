import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
from scraper import get_star_info

# 載入環境變數 (讓電腦讀取 .env)
load_dotenv()

# 初始化 Flask 應用程式 (這就是 Render 在找的那個 app！)
app = Flask(__name__)

# 從環境變數抓取 LINE 的密碼
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# 確認密碼有沒有抓到
if channel_access_token is None or channel_secret is None:
    print("請確認 .env 檔案或 Render 環境變數是否設定正確！")

# 設定 LINE Bot 的連線工具
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# 這是 LINE 傳訊息給我們時的入口 (Webhook)
@app.route("/callback", methods=['POST'])
def callback():
    # 抓取簽名 (這是為了確認訊息真的是 LINE 傳來的)
    signature = request.headers['X-Line-Signature']

    # 抓取訊息內容
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 處理訊息
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 當機器人收到「文字訊息」時，會執行這裡
@app.route("/", methods=['GET'])
def home():
    return "Hello World! Your Line Bot is running."

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text # 用戶輸入的字，例如 "合歡山"
    
    # 呼叫爬蟲程式去查天氣
    reply_text = get_star_info(user_msg)

    # 把查到的結果回傳給用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# 程式入口
if __name__ == "__main__":
    app.run()