import json, requests, time, json, random
import datetime 
import __facebookToolsV2
from utils import digitToChar, str_base, parse_cookie_string, Headers, formAll, mainRequests

def formatResults(type, text):
     if (type == "error"):
          return {
               type: text
          }
     elif (type == "success"):
          return {
               type: 1,
               "messages": text
          }
     else:
          return {
               "unknown": 1
          }
class thread:

     def __init__(self, threadID, dataFB):
          
          self.threadID = threadID
          self.dataFB = dataFB
     
     def addUserToAdminThread(self, idUser, statusChoice): # Thêm admin mới trong nhóm
         
          dataForm = formAll(self.dataFB, requireGraphql=False)
          dataForm["thread_fbid"] = str(self.threadID)
          dataForm["admin_ids[0]"] = str(idUser)
          dataForm["add"] = statusChoice
     
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/save_admins/?dpr=1", dataForm, self.dataFB["cookieFacebook"])).text.split("for (;;);")[1])
         
          if sendRequests.get("error"):
               error = sendRequests["error"]
               if error == 1976004:
                    return formatResults("error", "Bạn không phải là quản trị viên.")
               elif error == 1357031:
                    return formatResults("error", "Chủ đề này không phải là một cuộc trò chuyện nhóm.")
               else:
                    return formatResults("error", "Lỗi không xác định.")
          else:
               return formatResults("success", "Thêm admin cho nhóm thành công.")
     
     def changeNicknameUser(self, idUser, NewNickname): # Thay đổi biệt danh người dùng
     
          dataForm = formAll(self.dataFB, requireGraphql=False)
          dataForm["nickname"] = NewNickname
          dataForm["participant_id"] = idUser
          dataForm["thread_or_other_fbid"] = self.threadID
     
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/save_thread_nickname/?source=thread_settings&dpr=1", dataForm, self.dataFB["cookieFacebook"])).text.split("for (;;);")[1])
          
          if sendRequests.get("error"):
               error = sendRequests.get("error")
               if error == 1545014:
                    return formatResults("error", "Người dùng không tồn tại trong nhóm/cuộc trò chuyện.")
               elif error == 1357031:
                    return formatResults("error", "Người dùng không tồn tại.")
               else:
                    return formatResults("error", "Lỗi không xác định.")
          else:
               return formatResults("success", "Thay đổi biệt danh người dùng thành công.")
          
     def changeThreadEmoji(self, newEmoji): # Thay đổi biểu tượng cảm xúc nhanh 
     
          dataForm = formAll(self.dataFB, requireGraphql=False)
          dataForm["emoji_choice"] = newEmoji
          dataForm["thread_or_other_fbid"] = self.threadID
          
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/save_thread_emoji/?source=thread_settings&__pc=EXP1%3Amessengerdotcom_pkg", dataForm, self.dataFB["cookieFacebook"])).text.split("for (;;);")[1])
     
          if (sendRequests.get("error")):
               error = sendRequests.get("error")
               if error == 1357031:
                    return formatResults("error", "Không thể thay đổi trạng thái emoji của một cuộc trò chuyện không tồn tại.")
               else:
                    return formatResults("error", "Lỗi không xác định.")
          else:
               return formatResults("success", "Thay đổi biểu tượng cảm xúc nhanh thành công.")
     
     def changeNameThread(self, newNameThread): # Thay đổi tên nhóm
          
          randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
     
          dataForm = formAll(self.dataFB, requireGraphql=False)
          dataForm["client"] = "mercury"
          dataForm["action_type"] = "ma-type:log-message"
          dataForm["thread_id"] = ""
          dataForm["author_email"] = ""
          dataForm["action_type"] = ""
          dataForm["timestamp"] = int(time.time() * 1000)
          dataForm["timestamp_absolute"] = "Today"
          dataForm["author"] = "fbid:" + str(self.dataFB["FacebookID"])
          dataForm["is_unread"] = False
          dataForm["is_cleared"] = False
          dataForm["is_forward"] = False
          dataForm["is_filtered_content"] = False
          dataForm["is_filtered_content_bh"] = False
          dataForm["is_filtered_content_account"] = False
          dataForm["is_filtered_content_quasar"] = False
          dataForm["is_filtered_content_invalid_app"] = False
          dataForm["is_spoof_warning"] = False
          dataForm["thread_fbid"] = str(self.threadID)
          dataForm["thread_name"] = newNameThread
          dataForm["thread_id"] = str(self.threadID)
          dataForm["source"] = "source:chat:web"
          dataForm["source_tags[0]"] = "source:chat"
          dataForm["client_thread_id"] = "root:" + randomNumber
          dataForm["offline_threading_id"] = randomNumber
          dataForm["message_id"] = randomNumber
          dataForm["threading_id"] = "<{}:{}-{}@mail.projektitan.com>".format(int(time.time() * 1000), int(random.random() * 4294967295), hex(int(random.random() * 2 ** 31))[2:])
          dataForm["ephemeral_ttl_mode"] = "0"
          dataForm["manual_retry_cnt"] = "0"
          dataForm["ui_push_phase"] = "V3"
          dataForm["log_message_type"] = "log:thread-name"
          # dataForm["thread_name"] = newNameThread
          # dataForm["thread_id"] = self.threadID
     
     
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/set_thread_name/", dataForm, self.dataFB["cookieFacebook"])).text.split("for (;;);")[1])
     
          if (sendRequests.get("error")):
               error = sendRequests.get("error")
               if error == 1545012:
                    return formatResults("error", "Bạn không thể thay đổi tên nhóm khi bạn không phải là một thành viên của nhóm.")
               elif error == 1545003:
                    return formatResults("error", "Không thể thay đổi tên nhóm không tồn tại.")
          else:
               return formatResults("error", "Thay đổi tên nhóm thành công.")


""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):
 
     * DỮ LIỆU CHUNG:
          - setCookies: cookie tài khoản Facebook
          - threadID: ID của nhóm

     * Đối với: addUserToAdminThread
          - idUser: ID Facebook người dùng cần thêm làm quản trị viên nhóm
          - StatusChoice: Lựa chọn add hoặc không (True/False)
     
     * Đối với changeNicknameUser:
          - idUser: ID Facebook người dùng cần đổi biệt danh
          - NewNickname: biệt danh cần dặt cho người dùng đã được chỉ định
     
     * Đối với: changeThreadEmoji
          - newEmoji: biểu tượng cảm xúc cần đặt
     
     * Đối với: changeNameThread
          - newNameThread: Tên nhóm mới cần đặt 

* Code mẫu:
     
     _ = thread("<threadID>", __facebookToolsV2.dataGetHome("<setCookies>"))
     __ = _.changeThreadEmoji("🐛") # Đổi emoji nhanh của nhóm
     print(__)
           
* Kết quả trả về:
     
     Không có dữ liệu cụ thể.
     
     - Ghi chú: Nếu cảm thấy khó hiểu, hãy liên hệ với tui.

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 03:32 ngày 28/6/2023 • Cập nhật mới nhất: Không có dữ liệu: 00:01 07/08/2023
✓Tôn trọng tác giả ❤️
"""
