import requests, attr, json, time, random
 
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

def dataSplit(string1, string2, numberSplit1, numberSplit2, HTML):
     return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2]

def dataGetHome(setCookies):
     
     mainRequests = {
               "headers": {
                    "authority": "m.facebook.com",
                    "user-agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
               },
               "timeout": 60000,
               "url": "https://www.facebook.com/",
               "cookies": parse_cookie_string(setCookies),
               "verify": True
     }
     
     sendRequests = requests.get(**mainRequests).text
     
     fb_dtsg = dataSplit("token\":\"", "\"", 2, 0, sendRequests)
     fb_dtsg_ag = dataSplit("async_get_token\":\"", "\"", 1, 0, sendRequests)
     jazoest = dataSplit("jazoest=", "\"", 1, 0, sendRequests)
     LSD = dataSplit("LSD\",[],{\"token\":\"", "\"", 1, 0, sendRequests)
     hash = dataSplit("hash\":\"", "\"", 1, 0, sendRequests)
     sessionID = dataSplit("sessionId\":\"", "\"", 1, 0, sendRequests)
     clientID = dataSplit("clientID\":\"", "\"", 1, 0, sendRequests)
     appID = dataSplit("\"appId\":", ",", 1, 0, sendRequests)
     clientRevision = dataSplit("client_revision\":", ",", 1, 0, sendRequests)
     
     return {
          "fb_dtsg": fb_dtsg,
          "fb_dtsg_ag": fb_dtsg_ag,
          "jazoest": jazoest,
          "lsd": LSD,
          "hash": hash,
          "sessionID": sessionID,
          "clientID": clientID,
          "appID": appID,
          "client_revision": clientRevision,
          "FacebookID": setCookies.split("c_user=")[1].split(";")[0],
          "cookieFacebook": setCookies
     }

def getAllThreadList(dataFB):

     __reg = attr.ib(0).counter
     _revision = attr.ib()
     __reg += 1
     randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
     dataForm = {}
     
     dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
     dataForm["jazoest"] = dataFB["jazoest"]
     dataForm["__a"] = 1
     dataForm["__user"] =str(dataFB["FacebookID"])
     dataForm["__req"] = str_base(__reg, 36) 
     dataForm["__rev"] = dataFB["client_revision"]
     dataForm["av"] = dataFB["FacebookID"]
     dataForm["queries"] = json.dumps({
          "o0": {
               "doc_id": "1349387578499440",
               "query_params": {
                    "thread_and_message_id": {
                         "limit": 1,
                         "before": None,
                         "tags": ["INBOX"],
                         "includeDeliveryReceipts": False,
                         "includeSeqID": True,
                    }
               }
          }
     })
     
     mainRequests = {
               "headers": Headers(dataFB["cookieFacebook"], dataForm),
               "timeout": 60000,
               "url": "https://www.facebook.com/api/graphqlbatch/",
               "data": dataForm,
               "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
               "verify": True
     }
               
     sendRequests = requests.post(**mainRequests)
     return sendRequests

def typeCommand(commandUsed, threadID, dataGet):
     listData = []
     
     try: getData = json.loads(dataGet)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
     except: return getData["o0"]["error"]
     for getNeedIDThread in getData:
          if (str(getNeedIDThread["thread_key"]["thread_fbid"]) == str(threadID)):
               dataThread = getNeedIDThread
               
     # if (str(globals().keys()).find("dataThread") != 0):
          # dataThread = None
          
     if (dataThread != None):
          if (commandUsed == "getAdmin"): # Lấy id Admin Thread
               for dataID in dataThread["thread_admins"]:
                    listData.append(str(dataID["id"]))
               exportData = {
                    "adminThreadList": listData
               }
          elif (commandUsed == "threadInfomation"): # Lấy thông tin Thread
               threadInfoList = dataThread["customization_info"]
               exportData = {
                    "nameThread": dataThread["name"], 
                    "IDThread": threadID, 
                    "emojiThread": threadInfoList["emoji"],
                    "messageCount": dataThread["messages_count"],
                    "adminThreadCount": len(dataThread["thread_admins"]),
                    "memberCount": len(dataThread["all_participants"]["nodes"]),
                    "approvalMode": "Bật" if (dataThread["approval_mode"] != 0) else "Tắt",
                    "joinableMode": "Bật" if (dataThread["joinable_mode"]["mode"] != "0") else "Tắt",
                    "urlJoinableThread": dataThread["joinable_mode"]["link"]
               }
          elif (commandUsed == "exportMemberListToJson"): # Chuyển đổi dữ liệu member Thread
               getMemberList = dataThread["all_participants"]["nodes"]
               for exportMemberList in getMemberList:
                    dataUserThread = exportMemberList["messaging_actor"]
                    exportData = json.dumps({
                         dataUserThread["id"]: {
                              "nameFB": str(dataUserThread.get("name")),
                              "idFacebook": str(dataUserThread.get("id")),
                              "profileUrl": str(dataUserThread.get("url")),
                              "avatarUrl": str(dataUserThread["big_image_src"]["uri"]),
                              "gender": str(dataUserThread.get("gender")),
                              "usernameFB": str(dataUserThread.get("username"))
                         }
                    }, skipkeys=True, allow_nan=True, ensure_ascii=False, indent=5)
                    listData.append(exportData)
               exportData = listData
          else:
               exportData = {
                    "err": "no data"
               }
               
          return exportData
          
     else:
          return "Không lấy được dữ liệu ThreadList, đã xảy ra lỗi T___T"


""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):
 
     - dataFB: lấy từ dataGetHome
     - setCookies: Cookie account Facebook
     - commandUsed: Lệnh cần dùng (get thứ gì đó)[List Command: getAdmin, exportMemberListToJson, threadInfomation (Đọc command trên if, elif để hiểu rõ thêm)]
     - threadID: ID nhóm (Thread)
     - dataGet: lấy từ getAllThreadList(args - dữ liệu đầu vào)
     
* Kết quả trả về:
     
     Không có dữ liệu.
     
     - Ghi chú: nếu không hiểu gì hãy ib tui nhé hehe.

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 22:15 ngày 20/6/2023 • Cập nhật mới nhất: Không có dữ liệu
✓Tôn trọng tác giả ❤️
"""