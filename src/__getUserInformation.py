import json, requests, time, json, attr, random
# from LorenBot.plugins import __facebookToolsV2
import datetime
import __facebookToolsV2

def digitToChar(digit):
          if digit < 10:
               return str(digit)
          return chr(ord("a") + digit - 10)

def str_base(number, base):
     if number < 0:
          return "-" + str_base(-number, base)
     (d, m) = divmod(number, base)
     if d > 0:
          return str_base(d, base) + digitToChar(m)
     return digitToChar(m)

def parse_cookie_string(cookie_string):
     cookie_dict = {}
     cookies = cookie_string.split(";")

     for cookie in cookies:
          if "=" in cookie:
               key, value = cookie.split("=")
          else:
               pass
          try: cookie_dict[key] = value
          except: pass

     return cookie_dict

def Headers(setCookies, dataForm=None):
     headers = {}
     headers["Host"] = "www.facebook.com"
     headers["Connection"] = "keep-alive"
     if (dataForm != None):
          headers["Content-Length"] = str(len(dataForm))
     headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
     headers["Accept"] = "*/*"
     headers["Origin"] = "https://www.facebook.com"
     headers["Sec-Fetch-Site"] = "same-origin"
     headers["Sec-Fetch-Mode"] = "cors"
     headers["Sec-Fetch-Dest"] = "empty"
     headers["Referer"] = "https://www.facebook.com/"
     headers["Accept-Language"] = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"


def Main(dataFB, userID):
     __reg = attr.ib(0).counter
     _revision = attr.ib()
     __reg += 1
     dataForm = {}
     
     dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
     dataForm["jazoest"] = dataFB["jazoest"]
     dataForm["__a"] = 1
     dataForm["__user"] =str(dataFB["FacebookID"])
     dataForm["__req"] = str_base(__reg, 36) 
     dataForm["__rev"] = dataFB["client_revision"]
     dataForm["av"] = dataFB["FacebookID"]
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
✓Hoàn thành vào lúc 18:43 ngày 27/6/2023 • Cập nhật mới nhất: Không có dữ liệu
✓Tôn trọng tác giả ❤️
"""
