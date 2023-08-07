import requests, attr, json, time, random
import __facebookToolsV2
from utils import Headers, digitToChar, str_base, parse_cookie_string, formAll
     
def Main(dataFB, typeAdded, messageID, emojiChoice):

     dataForm = formAll(dataFB, docID=1491398900900362)
     dataForm["variables"] = json.dumps({"data": {
          "action": "ADD_REACTION" if (typeAdded == "add") else "REMOVE_REACTION",
          "client_mutation_id": "1",
          "actor_id": dataFB["FacebookID"],
          "message_id": str(messageID),
          "reaction": emojiChoice # random.choice(["🥺","😏", "✅","😎","😭", "🫥", "✈️", "✅", "🌚", "😵", "😮‍💨", "😷", "🥹", "😒", "🐧", "💩", "🍦", "👀", "💀", "🐣", "💔", "🫶🏻", "🪐", "🙈", "🐈‍⬛", "🦆", "🔪", "⚙️", "🧭", "📡", "💌", "⁉️", "💀"])
     }})
     dataForm["dpr"] = 1
     
     mainRequests = {
               "headers": Headers(dataFB["cookieFacebook"], dataForm),
               "timeout": 60000,
               "url": "https://www.facebook.com/webgraphql/mutation/",
               "data": dataForm,
               "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
               "verify": True
     }
               
     sendRequests = requests.post(**mainRequests)
     return sendRequests
     

""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):

     - dataFB: lấy từ __facebookToolsV2.dataGetHome(setCookies)
     - setCookies: Cookie account Facebook
     - typeAdded: "add" thêm reaction vào tin nhắn đó. "remove" để xoá reaction tại tin nhắn đó
     - messageID: messageID của tin nhắn
     - emojiChoice: emoji cần reaction vào tin nhắn (VD: 👍, 😭, 😎,....)(All emoji)

* Kết quả trả về:

     - Không có dữ liệu
     - Ghi chú: tùy thuộc vào nhiều trường hợp mà error có thể báo code lỗi và chi tiết khác nhau!

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 21:22 ngày 23/6/2023 • Cập nhật mới nhất: 7:52 20/7/2023
✓Tôn trọng tác giả ❤️
"""
