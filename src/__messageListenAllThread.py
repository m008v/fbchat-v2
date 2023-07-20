import json, requests, re, json
from bs4 import BeautifulSoup
import datetime
from LorenBot.plugins.utils import parse_cookie_string, dataSplit, clearHTML

def jsonFormat(idUserOrThread, getName, contentMessages, timeStampSent, DatetimeSent, timeHasPassed, formatType, unseenCount=None):
     return {
          "IDThread/User": idUserOrThread,
          "nameThread/User": getName,
          "ContentMessages": clearHTML(contentMessages.replace("</span", "")),
          "timeStampSent": timeStampSent,
          "datetimeSent": str(DatetimeSent),
          "timeHasPassed": timeHasPassed,
          "unseenCount": unseenCount,
          "__type": formatType
     }
     
          
def Listen(dataFB):
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
          "url": "https://m.facebook.com/messages/t/",
          "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
          "verify": True
     }
     
     sendRequests = requests.get(**mainRequests)
     cacheData = []
     classGetNameLength = sendRequests.text.count("<header><h3 class=\"")
     classGetNameValue = dataSplit("<header><h3 class=\"", "\"", 1, 0, sendRequests.text)
     for totalCount in range(1, classGetNameLength + 1):
          try:
               getName = dataSplit("<header><h3 class=\"", ">", totalCount, 1, sendRequests.text, 3, "<", 0)
               contentMessages = dataSplit("class=\"snippet ellipsis", ">", totalCount, 1, sendRequests.text, 3, "</span></header></div></div><div", 0)
               timeStampSent = dataSplit("<abbr data-store=\"&#123;&quot;time&quot;:", ",", totalCount, 0, sendRequests.text)
               DatetimeSent = datetime.datetime.fromtimestamp(int(timeStampSent))
               timeHasPassed= dataSplit("data-sigil=\"timestamp\">", "<", totalCount, 0, sendRequests.text)
               senderID = dataSplit("id=\"threadlist_row_", "\"", totalCount, 0, sendRequests.text)
               if (contentMessages.find("messageicons img") == 0):
                    contentMessages = "Đã gửi 1 ảnh."
               if (senderID.find("thread_fbid_") != 0):
                    formatType, idUserOrThread = "User", senderID.split("_")[3] 
               else:
                    formatType, idUserOrThread = "Thread", senderID.split("_")[2]
               if ((getName.find("(") != -1) & (getName.find(")") != -1)):
                    if (getName.split(")")[1] == ""):
                         try: 
                              unseenCount = int(dataSplit("(", ")", 1, 0, getName))
                              getName = getName.replace(f" ({unseenCount})", "")
                         except: unseenCount = "Error: "
                    else:
                         unseenCount = None
               else:
                    unseenCount = None
               cacheData.append(jsonFormat(idUserOrThread, getName, contentMessages, timeStampSent, DatetimeSent, timeHasPassed, formatType, unseenCount))
          finally:
               pass
     return json.dumps({
          "statusCode": sendRequests.status_code,
          "processingTime": sendRequests.elapsed.total_seconds(),
          "dataMessages": cacheData,
          "Author": "MinhHuyDev"
     }, skipkeys=True, allow_nan=True, ensure_ascii=False, indent=5)


""" Hướng dẫn sử dụng (Tutorial):

 * Dữ liệu yêu cầu (args):
 
     - dataFB: lấy từ __facebookToolsV2.dataGetHome
     - setCookies: cookie tài khoản FB (dùng cho __facebookToolsV2)

* Kết quả trả về:
     
     khi nhận tin nhắn thành công:
          {
               "statusCode": 200,
               "processingTime": 1.633165,
               "dataMessages": [
                    {
                         "IDThread/User": "96626398.......",
                         "nameThread/User": "Lor....",
                         "ContentMessages": "Có......",
                         "timeStampSent": "16898......",
                         "datetimeSent": "2023-07......",
                         "timeHasPassed": "Vừa.......",
                         "unseenCount": 9583,
                         "__type": "Thread"
                    },
                    ............
               ],
               "Author": "MinhHuyDev"
          }
     khi nhận tin nhắn thất bại:
          None
          
* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Hoàn thành vào lúc 23:26 ngày 20/7/2023 • Cập nhật mới nhất: -
✓Tôn trọng tác giả ❤️
"""