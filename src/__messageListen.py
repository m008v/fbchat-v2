import json, requests, re, json
from bs4 import BeautifulSoup
import __facebookToolsV2 
import datetime
from utils import parse_cookie_string, dataSplit, clearHTML
"""
Lời nói đầu, Xin NHẮC là đây là lấy tin nhắn từ m.facebook.com, chứ không phải từ
wss://edge-chat.facebook.com/chat (websocket) nên là CHẮC CHẮN sẽ có độ trễ (tùy thuộc vào tốc độ mạng của bạn)
Kí Tên: Nguyễn Minh Huy
"""

def jsonFormat(senderID, messageContents, messageID, overviewRequests):
     return {
          "status": overviewRequests.status_code,
          "processingTime": overviewRequests.elapsed.total_seconds(),
          "results": {
               "senderID": senderID,
               "messageContents": messageContents,
               "messageID": messageID
          },
          "Datetime": str(datetime.datetime.today())
     }

def Listen(dataFB, threadID, Url="https://m.facebook.com"):
     mainRequests = {
               "headers": {
                   "Host": "m.facebook.com",
                   "Connection": "keep-alive",
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                   "Sec-Fetch-Site": "none",
                   "Sec-Fetch-Mode": "navigate",
                   "Sec-Fetch-User": "?1",
                   "Sec-Fetch-Dest": "document",
                   "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
               },
               "timeout": 30,
               "url": "{}/messages/t/{}".format(Url, threadID), 
               "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
               "verify": True
     }
     
     dashboardHTML = {
          "senderID": ["data-store=\"&#123;&quot;timestamp&quot;:", ",&quot;author&quot;:", ",&quot;uuid&quot;:&quot;"],
          "messageID": [",&quot;uuid&quot;:&quot;", "&quot;"],
     }
     
     sendRequests = requests.get(**mainRequests)
     countHtmlTags = str(sendRequests.text).count("data-sigil=\"message-text") + 1
     for i in range(countHtmlTags):
          try:
               dataThreadMessage = dataSplit("data-sigil=\"message-text\">", "\" data-sigil=\"message-text\">", i, 0, sendRequests.text)
               senderID = dataSplit(dashboardHTML["senderID"][0], dashboardHTML["senderID"][1], i, 1, sendRequests.text, 3, dashboardHTML["senderID"][2], 0)
               messageID = dataSplit(dashboardHTML["messageID"][0], dashboardHTML["messageID"][1], i, 0, sendRequests.text)
               classValue = dataSplit("<div class=\"", "\">", 1, 0, dataThreadMessage)      
               messageContentsHTML = str(dataSplit("<div class=\"" + str(classValue) + "\">", "</div>", 1, 0, dataThreadMessage)).replace("&#064;","@").replace("&#039;","'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#123;","{").replace("&#125;","}")
               if (len(messageContentsHTML.split(">")) >= 1):
                    classValue = dataSplit("<div class=\"", "\">", 1, 0, messageContentsHTML)
                    try: messageContents = clearHTML(messageContentsHTML.split("<div class=\"" + classValue + "\">")[1].replace("<br /> ","\n"))
                    except: 
                         if (clearHTML(messageContentsHTML.split("<div class=\"" + classValue + "\">")[1]) == ""):
                              messageContents = "Ký tự đặc biệt hoặc file được gửi"
                         else:
                              messageContents = "Unknown"
                      
                    mainJsonFormat = {
                         "senderID": senderID,
                         "messageContents": messageContents,
                         "messageID": messageID,
                         "overviewRequests": sendRequests
                    }
                    
                    if (i == countHtmlTags - 1):
                         resultJson = jsonFormat(**mainJsonFormat)
                         return resultJson
          except Exception as errLog:
               pass

""" Hướng dẫn sử dụng (Tutorial):

 * Dữ liệu yêu cầu (args):
 
     - dataFB: lấy từ __facebookToolsV2.dataGetHome
     - setCookies: cookie tài khoản FB (dùng cho __facebookToolsV2)
     - threadID: ID Nhóm (Thread)

* Kết quả trả về:
     
     khi nhận tin nhắn thành công:
          {'status': 200, 'processingTime': 0.86..., 'results': {'senderID': '100091....', 'messageContents': 'Ng....', 'messageID': 'mid.$gABESRz00.......'}, 'Datetime': '2023-06-22 ......'}
     khi nhận tin nhắn thất bại:
          None
          
* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 12:01 ngày 22/6/2023 • Cập nhật mới nhất: 7:21 20/07/2023
✓Tôn trọng tác giả ❤️
"""
