try:
 from re import search as regex
 from time import sleep
 from datetime import datetime
 import json,os, random
 try: import __facebookToolsV2
 except: from LorenBot.plugins import __facebookToolsV2 
 import requests
 import attr
 import time, json
 from threading import Thread,local
 from threading import Thread
except Exception as errLOg:
 print("err: " + str(errLOg))
 pass
USER_AGENTS = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 (KHTML, like Gecko) Version/8.0.5 Safari/601.1.10", "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1", "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6"]

def Headers(setCookies, dataForm):
     headers = {}
     headers["Host"] = "www.facebook.com"
     headers["Connection"] = "keep-alive"
     headers["Content-Length"] = str(len(dataForm))
     headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
     headers["Accept"] = "*/*"
     headers["Origin"] = "https://www.facebook.com"
     headers["Sec-Fetch-Site"] = "same-origin"
     headers["Sec-Fetch-Mode"] = "cors"
     headers["Sec-Fetch-Dest"] = "empty"
     headers["Referer"] = "https://www.facebook.com/"
     headers["Accept-Language"] = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
     
     return headers
          
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
     
class api():
     def sendMessage(dataFB, contentSend, threadID, typeAttachment=None, attachmentID=None):
          __reg = attr.ib(0).counter
          _revision = attr.ib()
          __reg += 1
          randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
          dataForm = {}
          
          if (contentSend != None and contentSend != ""):
          
               dataForm["action_type"] = "ma-type:user-generated-message"
               dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
               dataForm["jazoest"] = dataFB["jazoest"]
               dataForm["__a"] = 1
               dataForm["__user"] =str(dataFB["FacebookID"])
               dataForm["__req"] = str_base(__reg, 36) 
               dataForm["__rev"] = dataFB["client_revision"]
               dataForm["client"] = "mercury"
               dataForm["body"] = str(contentSend)
               dataForm["author"] = "fbid:" + str(dataFB["FacebookID"])
               dataForm["is_unread"] = False
               dataForm["is_cleared"] = False
               dataForm["is_forward"] = False
               dataForm["is_filtered_content"] = False
               dataForm["is_filtered_content_bh"] = False
               dataForm["is_filtered_content_account"] = False
               dataForm["is_filtered_content_quasar"] = False
               dataForm["is_filtered_content_invalid_app"] = False
               dataForm["is_spoof_warning"] = False
               dataForm["thread_fbid"] = str(threadID)
               dataForm["timestamp"] =  int(time.time() * 1000)
               dataForm["timestamp_absolute"] = "Today"
               dataForm["source"] = "source:chat:web"
               dataForm["source_tags[0]"] = "source:chat"
               dataForm["client_thread_id"] = "root:" + randomNumber
               dataForm["offline_threading_id"] = randomNumber
               dataForm["message_id"] = randomNumber
               dataForm["threading_id"] = "<{}:{}-{}@mail.projektitan.com>".format(int(time.time() * 1000), int(random.random() * 4294967295), hex(int(random.random() * 2 ** 31))[2:])
               dataForm["ephemeral_ttl_mode"] = "0"
               dataForm["manual_retry_cnt"] = "0"
               dataForm["ui_push_phase"] = "V3"
               dataForm["replied_to_message_id"] = dataFB["messageID"]
               dataForm["has_attachment"] = True
               dictAttachment = {
                    "gif": "gif_ids",
                    "image": "image_ids",
                    "audio": "audio_ids",
                    "file": "file_ids",
                    "audio": "audio_ids",
                    None: "this is not a Attachment we requested, try again later (đây không phải là Tệp đính kèm mà chúng tôi đã yêu cầu, hãy thử lại sau)"
               }
               if (typeAttachment != None):
                    try:
                         dictItemAttachment = dictAttachment[typeAttachment]                     
                         if (attachmentID != None):
                              if ((str(type(attachmentID)).find("int") != -1) | (str(type(attachmentID)).find("str") != -1)):
                                   dataForm[dictItemAttachment + "[0]"] = attachmentID
                              elif (str(type(attachmentID)).find("list") != -1):
                                   for dataID, countPhoto in zip(attachmentID, range(0, len(attachmentID))):
                                        dataForm[dictItemAttachment + "[" + str(countPhoto) + "]"] = dataID
                         else:
                              pass
                    except:
                         pass      
                    
               mainRequests = {
                    "headers": Headers(dataFB["cookieFacebook"], dataForm),
                    "timeout": 5,
                    "url": "https://www.facebook.com/messaging/send/",
                    "data": dataForm,
                    "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
                    "verify": True
               }
                    
               sendRequests = json.loads(requests.post(**mainRequests).text.split("for (;;);")[1])

               return print(dataForm)
               if (sendRequests.get("error") != None):
                    return {
                         "errorCode": sendRequests["error"],
                         "errorSummary": sendRequests["errorSummary"],
                         "errorDescription": sendRequests["errorDescription"]
                    }
               else: 
                    return {
                         "threadID": sendRequests["payload"]["actions"][0]["thread_fbid"],
                         "messageID": sendRequests["payload"]["actions"][0]["message_id"],
                         "timeStamps": sendRequests["payload"]["actions"][0]["timestamp"]
                    }

""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):

     -setCookies: Cookie account Facebook
     - dataFB: lấy từ __facebookToolsV2.dataGetHome(setCookies)
     - contentSend: nội dung tin nhắn
     - threadID: ID nhóm cần gửi tin nhắn
     - typeAttachment: chọn loại tệp- đính kèm cần gửi (image, video, gif, file.....)
     - attachmentID: ID tệp đính kèm đã được upload lên từ __uploadImages (có thể dùng list để gửi nhiều Attachment cùng lúc. VD: [45647...., 5443754....., 54492115.....])

* Kết quả trả về:

     - khi gửi tin nhắn thành công: 
          {'threadID': '4805171782880318', 'messageID': 'mid.$gABESRz00DD6PA6t1pGI0mYsQ8FpX', 'timeStamps': 1687157091748}
     - khi tin nhắn gửi thất bại:
          {'errorCode': 1545003, 'errorSummary': 'Hành động không hợp lệ', 'errorDescription': 'Bạn không thể thực hiện hành động đó.'}
     
     - Ghi chú: tùy thuộc vào nhiều trường hợp mà error có thể báo code lỗi và chi tiết khác nhau!

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 13:53 ngày 19/6/2023 • Cập nhật mới nhất: 13:24 26/6/2023
✓Tôn trọng tác giả ❤️
"""
