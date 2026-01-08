import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, QuickReply, QuickReplyButton, MessageAction,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, PostbackAction
)
from dotenv import load_dotenv


from scraper_final import get_weekly_star_info, get_impromptu_star_info, all_locations

# 載入環境變數
load_dotenv()

app = Flask(__name__)

channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

if channel_access_token is None or channel_secret is None:
    print("請確認 .env 檔案或 Render 環境變數是否設定正確！")

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# --- 資料準備：區域分類字典 ---
# 這是為了讓使用者先選區域，再選地點
region_map = {
    "北部": [
        "F010", "F022", "F023", "F011", "F012", "F013", "F014", "F001"
    ],
    "中部": [
        "F019", "F018", "F020", "F021", "F002", "F016", "F004", "F003"
    ],
    "南部": [
        "F015", "F017", "F024", "F025", "F026", "F007", "F009", "F008", "F005", "F006"
    ]
}

# 一張通用的星空圖，用於輪播卡片的封面 (你可以換成自己的圖片網址)
DEFAULT_IMG_URL = "https://images.unsplash.com/photo-1519681393784-d120267933ba?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Starry Night Bot is Running!"

# ==========================================
# 1. 處理「文字訊息」 (入口)
# ==========================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 無論使用者打什麼，都先跳出「選擇區域」的快速選單
    # 這也是未來 Rich Menu 按鈕可以觸發的動作
    
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=PostbackAction(label="北部地區", data="action=select_area&area=北部")),
        QuickReplyButton(action=PostbackAction(label="中部地區", data="action=select_area&area=中部")),
        QuickReplyButton(action=PostbackAction(label="南部地區", data="action=select_area&area=南部")),
    ])

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="請選擇您想去的觀星區域：", quick_reply=quick_reply)
    )

# ==========================================
# 2. 處理「按鈕點擊」 (核心邏輯)
# ==========================================
@handler.add(PostbackEvent)
def handle_postback(event):
    # 解析回傳的 data (例如: "action=select_area&area=北部")
    data = event.postback.data
    params = dict(x.split('=') for x in data.split('&'))
    action = params.get('action')

    # --- 情境 A: 使用者選了「區域」，要產生「地點輪播卡片」 ---
    if action == 'select_area':
        area = params.get('area')
        pids = region_map.get(area, [])
        
        columns = []
        for pid in pids:
            name = all_locations.get(pid, "未知地點")
            
            # 建立單張卡片 (CarouselColumn)
            column = CarouselColumn(
                thumbnail_image_url=DEFAULT_IMG_URL, # 這裡放星空圖
                title=name,
                text=f"{area}熱門觀星點",
                actions=[
                    # 按鈕 1: 查一週
                    PostbackAction(
                        label="📅 未來一週指南",
                        data=f"action=weekly&pid={pid}&name={name}"
                    ),
                    # 按鈕 2: 查今晚
                    PostbackAction(
                        label="🚀 今晚時段分析",
                        data=f"action=impromptu&pid={pid}&name={name}"
                    )
                ]
            )
            columns.append(column)

        # 建立輪播訊息
        carousel_template = CarouselTemplate(columns=columns)
        template_message = TemplateSendMessage(
            alt_text=f"請選擇{area}觀星地點",
            template=carousel_template
        )
        
        line_bot_api.reply_message(event.reply_token, template_message)

    # --- 情境 B: 使用者選了「未來一週指南」 ---
    elif action == 'weekly':
        name = params.get('name')
        # 顯示「查詢中...」讓用戶知道機器人活著 (選用)
        # 呼叫 scraper.py 的函式
        result = get_weekly_star_info(name)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result)
        )

    # --- 情境 C: 使用者選了「今晚時段分析」 ---
    elif action == 'impromptu':
        pid = params.get('pid')
        name = params.get('name')
        
        # 呼叫 scraper.py 的函式 (即時爬蟲)
        result = get_impromptu_star_info(pid, name)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result)
        )

if __name__ == "__main__":
    app.run()