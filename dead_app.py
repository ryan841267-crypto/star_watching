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
from weather_and_map import get_weekly_star_info, get_impromptu_star_info, all_locations

load_dotenv()

app = Flask(__name__)

channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# ==========================================
# 0. 資料與設定區
# ==========================================

# (A) 載入簡介資料
SPOT_DESCRIPTIONS = {}
if os.path.exists("spot_descriptions.json"):
    with open("spot_descriptions.json", "r", encoding="utf-8") as f:
        SPOT_DESCRIPTIONS = json.load(f)

# (B) 圖片設定 (已根據你的 GitHub 設定修正)
GITHUB_BASE_URL = "https://raw.githubusercontent.com/ryan841267-crypto/star_watching/main/images/"

# 全域預設圖 (主選單封面)
DEFAULT_IMG_URL = f"{GITHUB_BASE_URL}default.jpg"

# 區域預設圖
REGION_DEFAULT_IMAGES = {
    "北部": "north_default.jpg",
    "中部": "central_default.jpg",
    "南部": "south_default.jpg"
}

# 已有專屬照片的地點 PID (這裡只留這兩個範例，你可以自己增減)
HAS_PHOTO_PIDS = [""] 

# (C) 歌詞與彩蛋設定
LYRICS_STAR_EYES = """看著夜晚的繁星，來首眼底星空吧!
<<歌詞複習>>

verse
妳好喜歡看我眼睛
妳說是宇宙的縮影
只要沒有分離天氣晴 能看見星星
我努力愛妳寵妳調整自己
我是鄰居還是伴侶
時間帶來殘忍結局
在愛情的隔壁住友情 界線太銳利
對不起就一刀切開所有親密

chorus
眼底星空 流星開始墜落
每一滴眼淚說著妳要好好走
轉過身跌入黑洞 看著天長地久變兩種漂泊
男人流淚比流血加倍心痛
眼底星空 流星跌落手中
我緊緊握著抬頭向上天祈求
願妳先找到溫柔 有人包紮傷口也擋住寂寞
謝謝妳陪我陪愛聽雨追風

verse
用三年去維繫感情
用三秒鐘結束關係
剩回憶能回去 能溫習 能把妳抱緊
就算愛燒成灰燼揚起變烏雲

chorus
眼底星空 流星開始墜落
每一滴眼淚說著妳要好好走
轉過身跌入黑洞 看著天長地久變兩種漂泊
男人流淚比流血加倍心痛
眼底星空 流星跌落手中
我緊緊握著抬頭向上天祈求
願妳先找到溫柔 有人包紮傷口也擋住寂寞
謝謝妳陪我陪愛聽雨追風

眼底星空 流星跌落手中
我緊緊握著抬頭向上天祈求
願妳先找到溫柔 有人包紮傷口也擋住寂寞
謝謝妳陪我陪愛聽雨追風

outro
謝謝他給你給愛另一個星空"""

EASTER_EGGS = {
    "心情不好": "選個觀星點，抬頭看看星空吧，宇宙這麼大，煩惱其實很渺小的！🌌",
    "眼底星空": LYRICS_STAR_EYES
}

# (D) 區域分類
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
# A. 產生選單函式 (只回傳物件，不發送)
# ==========================================
def get_main_menu_flex():
    flex_content = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": DEFAULT_IMG_URL,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "uri": "http://linecorp.com/"}
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
    return FlexSendMessage(alt_text="請選擇觀星區域", contents=flex_content)

# ==========================================
# B. 處理「加好友」&「文字訊息」 (核心邏輯)
# ==========================================

@handler.add(FollowEvent)
def handle_follow(event):
    # 加好友時，直接丟選單
    menu_message = get_main_menu_flex()
    line_bot_api.reply_message(event.reply_token, menu_message)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply_list = []
    
    # 1. 檢查是否觸發彩蛋 (只要句子裡包含關鍵字就觸發)
    for keyword, response_text in EASTER_EGGS.items():
        if keyword in user_text:
            reply_list.append(TextSendMessage(text=response_text))
            break # 找到一個關鍵字就停，避免一次回太多
    
    # 2. 無論有無觸發彩蛋，最後都要接上主選單
    menu_message = get_main_menu_flex()
    reply_list.append(menu_message)
    
    # 3. 發送 (可能是 [選單] 或是 [文字, 選單])
    line_bot_api.reply_message(event.reply_token, reply_list)

# ==========================================
# C. 處理「按鈕點擊」 (三層式圖片邏輯)
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
            
            # --- 💡 圖片判斷邏輯 ---
            specific_photo = f"{pid}.jpg"
            region_photo = REGION_DEFAULT_IMAGES.get(area)
            
            if pid in HAS_PHOTO_PIDS:
                # 第一優先：專屬照片
                image_url = f"{GITHUB_BASE_URL}{specific_photo}?v=1"
            elif region_photo:
                # 第二優先：區域預設圖
                image_url = f"{GITHUB_BASE_URL}{region_photo}?v=1"
            else:
                # 第三優先：全域預設圖
                image_url = DEFAULT_IMG_URL
            # ----------------------

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