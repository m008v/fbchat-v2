import requests, json
import __facebookToolsV2 
from utils import digitToChar, str_base, parse_cookie_string, Headers, formAll
 
def Main(messageID, dataFB):

     dataForm = formAll(dataFB, requireGraphql=False)
     dataForm["message_id"] = messageID

     mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 5,
        "url": "https://www.facebook.com/messaging/unsend_message/",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "verify": True
    }
     
     sendRequests = json.loads(requests.post(**mainRequests).text.split("for (;;);")[1])

     if (sendRequests.get("error")):
          return Exception({"error": str(sendRequests)})
     else:
          return {
               "success": 1,
               "messages": "Thu hồi tin nhắn thành công."
          }

""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):

     -setCookies: Cookie account Facebook
     - dataFB: lấy từ __facebookToolsV2.dataGetHome(setCookies)
     - messageID: Message ID của tin nhắn (Example: mid.$gABESRz00DD6........)

* Kết quả trả về:

     - Không có dữ liệu
     
     - Ghi chú: tùy thuộc vào nhiều trường hợp mà error có thể báo code lỗi và chi tiết khác nhau!

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 09:36 ngày 30/6/2023 • Cập nhật mới nhất: 8:00 20/7/2023
✓Tôn trọng tác giả ❤️
"""
