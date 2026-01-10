import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, PostbackAction,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, 
    FollowEvent, FlexSendMessage,
    # [新增] 引入 QuickReply 與位置訊息相關模組
    QuickReply, QuickReplyButton, LocationAction, LocationMessage
)
from dotenv import load_dotenv

# 引用你的爬蟲主程式
# [修改] 新增引用 LOCATION_COORDS 和 get_real_walking_info
from scraper_final import (
    get_weekly_star_info, 
    get_impromptu_star_info, 
    all_locations, 
    update_weekly_csv,
    LOCATION_COORDS,       # 座標資料
    get_real_walking_info  # 計算邏輯
)


# 先去翻閱「機密筆記本」（.env 檔），把裡面寫的密碼讀進記憶體裡。
load_dotenv()

# 建立一個 Flask 應用程式實例。
app = Flask(__name__)

# 從剛才載入的環境變數中，抓出 Token 和 Secret 這兩把關鍵鑰匙。
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# line_bot_api：使用的是 Access Token。
# 任務：負責主動做事。
# 例如：回覆訊息 (reply_message)、推播訊息 (push_message)、或是取得使用者大頭貼。

# handler (負責「聽」)：使用的是 Secret。
# 負責接收與分配。
# 當 Line 傳訊息過來（Webhook），它負責檢查安全簽章，然後判斷這是「文字訊息」還是「貼圖訊息」，再指派給對應的函式去處理。
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# ==========================================
# 0. 資料與設定區
# ==========================================

# [新增] 使用者暫存記憶體 (用來記住誰剛剛點了哪個景點，放在 app.py 管理)
USER_SESSION = {}

# (A) 載入簡介資料
SPOT_DESCRIPTIONS = {}
if os.path.exists("spot_descriptions.json"):
    with open("spot_descriptions.json", "r", encoding="utf-8") as f:
        SPOT_DESCRIPTIONS = json.load(f)

# (B) 圖片設定
GITHUB_BASE_URL = "https://raw.githubusercontent.com/ryan841267-crypto/star_watching/main/images/"
DEFAULT_IMG_URL = f"{GITHUB_BASE_URL}default.jpg"

REGION_DEFAULT_IMAGES = {
    "北部": "north_default.jpg",
    "中部": "central_default.jpg",
    "南部": "south_default.jpg"
}
HAS_PHOTO_PIDS = [""] 

# (C) 歌詞與彩蛋
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

# Line 傳過來的每一則訊息，都會在信封（HTTP Header）上貼一個防偽標籤，叫做 X-Line-Signature。
# 這個標籤是用 Channel Secret 加密算出來的。
# handler（守門員）拿著剛剛收到的「信件內容 (body)」和「防偽標籤 (signature)」，進行複雜的密碼學比對。
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True) # 確保是純文字字串，因為後面的驗證函式需要吃文字。
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 測試通道
@app.route("/", methods=['GET'])
def home():
    return "Star Bot Running"

# ==========================================
# A. 產生選單
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
# B. 處理訊息
# ==========================================

@handler.add(FollowEvent)
def handle_follow(event):
    menu_message = get_main_menu_flex()
    line_bot_api.reply_message(event.reply_token, menu_message)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply_list = []
    
    for keyword, response_text in EASTER_EGGS.items():
        if keyword in user_text:
            reply_list.append(TextSendMessage(text=response_text))
            break 
    
    menu_message = get_main_menu_flex()
    reply_list.append(menu_message)
    
    line_bot_api.reply_message(event.reply_token, reply_list)

# ==========================================
# C. 處理按鈕
# ==========================================
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    params = dict(x.split('=') for x in data.split('&'))
    action = params.get('action')

    if action == 'select_area':
        area = params.get('area')
        pids = region_map.get(area, [])
        columns = []
        
        for pid in pids[:10]: # Limit to 10
            name = all_locations.get(pid, "未知")
            specific_photo = f"{pid}.jpg"
            region_photo = REGION_DEFAULT_IMAGES.get(area)
            
            if pid in HAS_PHOTO_PIDS:
                image_url = f"{GITHUB_BASE_URL}{specific_photo}?v=1"
            elif region_photo:
                image_url = f"{GITHUB_BASE_URL}{region_photo}?v=1"
            else:
                image_url = DEFAULT_IMG_URL

            column = CarouselColumn(
                thumbnail_image_url=image_url,
                title=name,
                text=f"{area}熱門觀星點",
                actions=[
                    PostbackAction(label="未來一週指南", data=f"action=weekly&pid={pid}&name={name}"),
                    PostbackAction(label="今晚觀星分析", data=f"action=impromptu&pid={pid}&name={name}"),
                    # [修改] 第三個按鈕改為「觀星景點資訊」，並使用 info action
                    PostbackAction(label="觀星景點資訊", data=f"action=info&pid={pid}&name={name}")
                ]
            )
            columns.append(column)
        
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text=f'{area}觀星點', template=CarouselTemplate(columns=columns))
        )

    elif action == 'weekly':
        name = params.get('name')
        res = get_weekly_star_info(name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    elif action == 'impromptu':
        pid = params.get('pid')
        name = params.get('name')
        res = get_impromptu_star_info(pid, name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    # [修改] 處理景點資訊與位置請求 (取代原本的 desc)
    elif action == 'info':
        pid = params.get('pid')
        name = params.get('name')
        user_id = event.source.user_id # 取得使用者 ID
        
        # 1. 取得景點介紹
        desc = SPOT_DESCRIPTIONS.get(pid, "暫無詳細資料")
        
        # 2. 存入 Session，讓後面的位置訊息知道目標是誰
        USER_SESSION[user_id] = {"pid": pid, "name": name}

        # 3. 回覆介紹 + 引導傳送位置的 QuickReply
        reply_text = (
            f"📖 【{name}】\n\n{desc}\n\n"
            f"想知道步行過去要多久嗎？\n"
            f"請點擊下方按鈕👇"
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply_text,
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=LocationAction(label="📍 傳送目前位置"))
                ])
            )
        )

# [新增] D. 處理位置訊息 (計算距離與導航)
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    user_id = event.source.user_id
    
    # 1. 檢查使用者是否有正在進行的查詢
    session_data = USER_SESSION.get(user_id)
    if not session_data:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請先從選單點選「觀星景點資訊」，我才知道你要去哪裡喔！")
        )
        return

    # 2. 取得資料
    target_pid = session_data['pid']
    target_name = session_data['name']
    user_lat = event.message.latitude
    user_lng = event.message.longitude
    
    # 3. 取得目的地座標 (從 scraper_final 匯入的資料庫查)
    dest_coords = LOCATION_COORDS.get(target_pid)
    
    if not dest_coords:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"抱歉，系統暫時缺少【{target_name}】的座標資料，無法計算距離。")
        )
        # 清除 Session
        if user_id in USER_SESSION: del USER_SESSION[user_id]
        return

    # 4. 呼叫 Google Distance Matrix API (呼叫 scraper_final 裡的函式)
    dist_text, time_text = get_real_walking_info(
        user_lat, user_lng,
        dest_coords[0], dest_coords[1]
    )
    
    if time_text:
        # 產生 Google Maps 導航連結 (使用官方 Universal URL 格式)
        map_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&origin={user_lat},{user_lng}"
            f"&destination={dest_coords[0]},{dest_coords[1]}"
            f"&travelmode=walking"
        )

        # 你的指定格式回覆
        reply_msg = (
            f"🚶 目前步行至【{target_name}】只要 {time_text} 哦，揪團走路去觀星吧!\n\n\n"
            f"詳情請查看下方導航連結!\n"
            f"{map_url}"
        )
    else:
        reply_msg = "⚠️ 計算失敗，可能是 Google API 連線問題或距離太遠無法步行到達。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
    
    # 5. 任務結束，清除記憶
    if user_id in USER_SESSION:
        del USER_SESSION[user_id]

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)