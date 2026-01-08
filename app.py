import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, PostbackAction,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, 
    FollowEvent, FlexSendMessage
)
from dotenv import load_dotenv

# 引用你的爬蟲主程式
from scraper_final import get_weekly_star_info, get_impromptu_star_info, all_locations

load_dotenv()

app = Flask(__name__)

channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# --- 1. 載入簡介資料 ---
SPOT_DESCRIPTIONS = {}
if os.path.exists("spot_descriptions.json"):
    with open("spot_descriptions.json", "r", encoding="utf-8") as f:
        SPOT_DESCRIPTIONS = json.load(f)

# --- 2. 圖片設定 (請修改這裡) ---

# GitHub 圖片基地網址
# 格式: https://raw.githubusercontent.com/帳號/專案名/main/images/
GITHUB_BASE_URL = "https://raw.githubusercontent.com/ryan841267-crypto/star_watching/main/images/"

# (A) 全域預設圖：用於「主選單」以及「完全找不到圖時」的備案
# 建議你在 images 資料夾放一張 default.jpg，然後把下一行註解拿掉：
DEFAULT_IMG_URL = f"{GITHUB_BASE_URL}default.jpg"
# ⬇️ 暫時先用 Unsplash 當預設，等你上傳 default.jpg 後可以換掉上面那行
# DEFAULT_IMG_URL = "https://images.unsplash.com/photo-1519681393784-d120267933ba?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80"

# (B) 區域預設圖：該區域的統一樣式
REGION_DEFAULT_IMAGES = {
    "北部": "north_default.jpg",
    "中部": "central_default.jpg",
    "南部": "south_default.jpg"
}

# (C) 已有專屬照片的地點 PID
# 如果你有上傳 F022.jpg (小油坑)，就把它加進這個清單
HAS_PHOTO_PIDS = [] # 範例，你可以隨時新增

# --- 3. 區域分類 ---
region_map = {
    "北部": ["F010", "F022", "F023", "F011", "F012", "F013", "F001"],
    "中部": ["F014", "F019", "F018", "F020", "F021", "F002", "F016", "F004", "F003"],
    "南部": ["F015", "F017", "F024", "F025", "F026", "F007", "F009", "F008", "F005", "F006"]
}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Star Bot Running"

# ==========================================
# A. 處理「文字訊息」&「加好友」 (Flex Message 主選單)
# ==========================================
def send_region_menu(reply_token):
    # 使用全域預設圖作為主選單封面
    flex_content = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": DEFAULT_IMG_URL, # 使用預設圖
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {
                "type": "uri",
                "uri": "http://linecorp.com/"
            }
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🌌 觀星指南",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                },
                {
                    "type": "text",
                    "text": "請選擇您想前往的觀星區域",
                    "size": "sm",
                    "color": "#aaaaaa",
                    "wrap": True
                }
            ],
            "backgroundColor": "#0f1c30"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {"type": "postback", "label": "北部地區", "data": "action=select_area&area=北部"},
                    "color": "#4e6d8d"
                },
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {"type": "postback", "label": "中部地區", "data": "action=select_area&area=中部"},
                    "color": "#4e6d8d"
                },
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {"type": "postback", "label": "南部地區", "data": "action=select_area&area=南部"},
                    "color": "#4e6d8d"
                }
            ],
            "flex": 0,
            "backgroundColor": "#0f1c30"
        }
    }

    line_bot_api.reply_message(
        reply_token,
        FlexSendMessage(alt_text="請選擇觀星區域", contents=flex_content)
    )

@handler.add(FollowEvent)
def handle_follow(event):
    send_region_menu(event.reply_token)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    send_region_menu(event.reply_token)

# ==========================================
# B. 處理「按鈕點擊」 (三層式圖片邏輯)
# ==========================================
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    params = dict(x.split('=') for x in data.split('&'))
    action = params.get('action')

    # 1. 選區域 -> 顯示地點輪播
    if action == 'select_area':
        area = params.get('area')
        pids = region_map.get(area, [])
        columns = []
        
        for pid in pids:
            name = all_locations.get(pid, "未知")
            
            # --- 💡 圖片判斷邏輯開始 ---
            specific_photo = f"{pid}.jpg"
            region_photo = REGION_DEFAULT_IMAGES.get(area)
            
            # 第一優先：是否有專屬照片?
            if pid in HAS_PHOTO_PIDS:
                image_url = f"{GITHUB_BASE_URL}{specific_photo}?v=1"
            # 第二優先：是否有區域預設圖?
            elif region_photo:
                image_url = f"{GITHUB_BASE_URL}{region_photo}?v=1"
            # 第三優先：用全域預設圖
            else:
                image_url = DEFAULT_IMG_URL
            # --------------------------

            column = CarouselColumn(
                thumbnail_image_url=image_url,
                title=name,
                text=f"{area}熱門觀星點",
                actions=[
                    PostbackAction(label="未來一週指南", data=f"action=weekly&pid={pid}&name={name}"),
                    PostbackAction(label="今晚觀星分析", data=f"action=impromptu&pid={pid}&name={name}"),
                    PostbackAction(label="景點簡略介紹", data=f"action=desc&pid={pid}&name={name}")
                ]
            )
            columns.append(column)
        
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text=f'{area}觀星點', template=CarouselTemplate(columns=columns))
        )

    # 2. 未來一週
    elif action == 'weekly':
        name = params.get('name')
        res = get_weekly_star_info(name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    # 3. 今晚時段
    elif action == 'impromptu':
        pid = params.get('pid')
        name = params.get('name')
        res = get_impromptu_star_info(pid, name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    # 4. 景點簡介
    elif action == 'desc':
        pid = params.get('pid')
        name = params.get('name')
        desc = SPOT_DESCRIPTIONS.get(pid, "暫無詳細資料")
        line_bot_api.reply_message(
            event.reply_token, 
            TextSendMessage(text=f"📖 【{name}】\n\n{desc}")
        )

if __name__ == "__main__":
    app.run()
