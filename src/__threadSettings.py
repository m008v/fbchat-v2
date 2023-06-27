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


def formAll(dataFB):
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

     return dataForm
def addUserToAdminThread(threadID, idUser, statusChoice, dataFB): # Thêm admin mới trong nhóm
    
    dataForm = formAll(dataFB)

    dataForm["thread_fbid"] = str(threadID)
    dataForm["admin_ids[0]"] = str(idUser)
    dataForm["add"] = statusChoice

    mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 5,
        "url": "https://www.facebook.com/messaging/save_admins/?dpr=1",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "verify": True
    }

    sendRequests = json.loads(requests.post(**mainRequests).text.split("for (;;);")[1])
    if sendRequests.get("error"):
        error = sendRequests["error"]
        if error == 1976004:
              return Exception({"error": "Không thể thay đổi trạng thái quản trị viên: bạn không phải là quản trị viên."})
        elif error == 1357031:
              return Exception({"error": "Không thể thay đổi trạng thái quản trị viên: chủ đề này không phải là một cuộc trò chuyện nhóm."})
        else:
              return Exception({"error": "Không thể thay đổi trạng thái quản trị viên: lỗi không xác định."})
    else:
         return {
              "success": 1,
              "messages": "Thêm admin cho nhóm thành công"
         }

def changeNicknameUser(threadID, idUser , NewNickname, dataFB): # Thay đổi biệt danh người dùng

     dataForm = formAll(dataFB)

     dataForm["nickname"] = NewNickname
     dataForm["participant_id"] = idUser
     dataForm["thread_or_other_fbid"] = threadID

     mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 5,
        "url": "https://www.facebook.com/messaging/save_thread_nickname/?source=thread_settings&dpr=1",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB33 ngày 28/6/2023 • Cập nhật mới nhất: Không có dữ liệu
✓Tôn trọng tác giả ❤️
"""
