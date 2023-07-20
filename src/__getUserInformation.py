import json, requests, time, json, attr, random
import datetime
import __facebookToolsV2
from utils import digitToChar, str_base, parse_cookie_string, Headers, formAll

def Main(dataFB, userID):
     
     dataForm = formAll(dataFB, requireGraphql=False)
     dataForm["ids[0]"] = userID


     mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 5,
        "url": "https://www.facebook.com/chat/user_info/",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "verify": True
    }
     
     sendRequests = requests.post(**mainRequests)
     try:
        jsonData = json.loads(sendRequests.text.split("for (;;);")[1])["payload"]["profiles"][str(userID)]
        
        idUser = jsonData.get("id")
        nameUser = jsonData.get("name")
        firstName = jsonData.get("firstName")
        Username = jsonData.get("vanity")
        thumbSrc = jsonData.get("thumnSrc")
        urlProfile = jsonData.get("uri")
        genderUser = jsonData.get("gender")
        alternateName = jsonData.get("alternateName")
        chatWithUSerIsNonFriend = jsonData.get("is_nonfriend_messenger_contact")

        if (genderUser == 1): genderUser = "Female (Nữ)"
        elif (genderUser == 2): genderUser = "Male (Nam)"
        else: genderUser = "Unknown (Không xác định)"

        return {
            "idUser": idUser,
            "nameUser": nameUser,
            "firstName": firstName,
            "Username": Username,
            "thumbSrc": thumbSrc,
            "urlProfile": urlProfile,
            "genderUser": genderUser,
            "alternateName": alternateName,
            "chatWithUSerIsNonFriend": chatWithUSerIsNonFriend
        }
     except:
          return {
               "err": 0
          }


""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):
 
     - dataFB: lấy từ __facebookToolsV2.dataGetHome(setCookies)
     - setCookies: Cookie account Facebook
     - userID: ID người dùng cần lấy thông tin
     
* Kết quả trả về:
     
     - Khi lấy dữ liệu thành công:

        {'idUser': '1...', 'nameUser': 'Priscilla......', ........}
     
     - Khi lấy dữ liệu thất bại:

        {'err': 0}
     
     - Ghi chú: nếu không hiểu gì hãy ib tui nhé hehe.

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 18:43 ngày 27/6/2023 • Cập nhật mới nhất: 7:16 20/7/2023
✓Tôn trọng tác giả ❤️
"""
