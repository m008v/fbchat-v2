import requests, attr, json, time, random
from utils import parse_cookie_string, dataSplit, formAll, mainRequests
 
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
     
     dictValueSaved = {}
     splitDataList = [
          # FORMAT: nameValue, stringData_1, stringData_2
          ["fb_dtsg", "[\"DTSGInitData\",[],{\"token\":\"", "\""],
          ["fb_dtsg_ag", "async_get_token\":\"", "\""],
          ["jazoest", "jazoest=", "\""],
          ["hash", "hash\":\"", "\""],
          ["sessionID", "sessionId\":\"", "\""],
          ["FacebookID", "\"actorID\":\"", "\""],
          ["clientRevision", "client_revision\":", ","]
     ]
     
     sendRequests = requests.get(**mainRequests).text
     
     for i in splitDataList:
          nameValue = i[0]
          try:
               exportValue = dataSplit(i[1], i[2], HTML=sendRequests, defaultValue=True)
          except:
               exportValue = "Unable to retrieve data for %s. It's possible that they have been deleted or modified." % nameValue
          dictValueSaved[nameValue] = exportValue
     dictValueSaved["cookieFacebook"] = setCookies
     
     return dictValueSaved

class fbTools:

     def __init__(self, dataFB, threadID):
         
          self.threadID = threadID
          self.dataGet = None
          self.dataFB = dataFB
          self.ProcessingTime = None
     
     def getAllThreadList(self): # Lấy dữ liệu những thành phần tin nhắn ở INBOX
     
          randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
          dataForm = formAll(self.dataFB, requireGraphql=0)
          # dataForm["av"] = self.dataFB["cookieFacebook"].split("c_user=")[1].split(";")[0]

          dataForm["queries"] = json.dumps({
               "o0": {
                    "doc_id": "3336396659757871",
                    "query_params": {
                         "limit": 1,
                         "before": None,
                         "tags": ["INBOX"], # INBOX, PENDING, ARCHIVED
                         "includeDeliveryReceipts": False,
                         "includeSeqID": True,
                    }
               }
          })
          
          sendRequests = requests.post(**mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, self.dataFB["cookieFacebook"]))
          # return sendRequests.text.split("{\"successful_results\"")[0]
          self.dataGet = sendRequests.text.split('{"successful_results"')[0]
          self.ProcessingTime = sendRequests.elapsed.total_seconds()
          self.last_seq_id = json.loads(self.dataGet)["o0"]["data"]["viewer"]["message_threads"]["sync_sequence_id"]
          return True
     
     def typeCommand(self, commandUsed): # Tổng hợp các lệnh có thể làm
          listData = []
          
          try: getData = json.loads(self.dataGet)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
          except: return json.loads(self.dataGet)["o0"]["errors"][0]["summary"]
          for getNeedIDThread in getData:
               if (str(getNeedIDThread["thread_key"]["thread_fbid"]) == str(self.threadID)):
                    dataThread = getNeedIDThread
          # if (str(globals().keys()).find("dataThread") != 0):>
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
                         "IDThread": self.threadID, 
                         "emojiThread": threadInfoList["emoji"],
                         "messageCount": dataThread["messages_count"],
                         "adminThreadCount": len(dataThread["thread_admins"]),
                         "memberCount": len(dataThread["all_participants"]["edges"]),
                         "approvalMode": "Bật" if (dataThread["approval_mode"] != 0) else "Tắt",
                         "joinableMode": "Bật" if (dataThread["joinable_mode"]["mode"] != "0") else "Tắt",
                         "urlJoinableThread": dataThread["joinable_mode"]["link"]
                    }
               elif (commandUsed == "exportMemberListToJson"): # Chuyển đổi dữ liệu member Thread
                    getMemberList = dataThread["all_participants"]["edges"]
                    for exportMemberList in getMemberList:
                         dataUserThread = exportMemberList["node"]["messaging_actor"]
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
     
     def getListThreadID(self): # Lấy danh sách threadID
          try:
               threadIDList = []
               threadNameList = []
               getData = json.loads(self.dataGet)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
               for getThreadID in getData:
                    if (getThreadID["thread_key"]["thread_fbid"] != None):
                         threadIDList.append(getThreadID["thread_key"]["thread_fbid"])
                         threadNameList.append(getThreadID["name"])
               return {
                    "threadIDList": threadIDList,
                    "threadNameList": threadNameList,
                    "countThread": len(threadIDList)
               }
          except Exception as errLog:
               return {
                    "ERR": str(errLog)
               }

""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):
 
     - setCookies: Cookie account Facebook
     - commandUsed: Lệnh cần dùng (get thứ gì đó)[List Command: getAdmin, exportMemberListToJson, threadInfomation (Đọc command trên if, elif để hiểu rõ thêm)]
     - threadID: ID nhóm (Thread)
  
* Code mẫu:
     
   _ = fbTools(dataGetHome("<setCookies>"), "<threadID>")
     print(_.getAllThreadList())
     print(_.typeCommand("getAdmin")) # Lấy thông tin List ID Admin của nhóm
    
* Kết quả trả về:
     
     - Khi lấy thành công:
          {'adminThreadList': ['9209278', '100025536690946', '100034821226355']}
     - Khi lấy thất bại:
          <description error from Facebook>
     
     - Ghi chú: nếu không hiểu gì hãy ib tui nhé hehe.

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 22:15 ngày 20/6/2023 • Cập nhật mới nhất: 23:47 07/01/2024
✓Tôn trọng tác giả ❤️
"""
