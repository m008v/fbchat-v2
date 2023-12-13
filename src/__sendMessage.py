from datetime import datetime
import json, random, requests, attr, time
from threading import Thread 
import __facebookToolsV2
from utils import Headers, digitToChar, str_base, parse_cookie_string, gen_threading_id, mainRequests, formAll
     
class api:
     
     def __init__(self):
     
          self.dataFB, self.content, self.ID, self.typeAttachment, self.attachmentID, self.typeChat, self.replyStatus, self.messageID = [None] * 8
          self.properties = ["is_unread", "is_cleared", "is_forward", "is_filtered_content", "is_filtered_content_bh", "is_filtered_content_account", "is_filtered_content_quasar", "is_filtered_content_invalid_app", "is_spoof_warning"]
          self.dictAttachment = {
               # key: value
               "gif": "gif_ids",
               "image": "image_ids",
               "video": "video_ids",
               "file": "file_ids",
               "audio": "audio_ids",
               None: "this is not a Attachment we requested, try again later (đây không phải là Tệp đính kèm mà chúng tôi đã yêu cầu, hãy thử lại sau)"
          }
          
          
     def updateDataAndSend(self, dataFB, contentSend, threadID, typeAttachment=None, attachmentID=None, typeChat=None, replyMessage=None, messageID=None):
          
          self.dataFB = dataFB # --> data from home Facebook
          self.content = str(contentSend) # --> contents message
          self.ID = str(threadID) # --> ID of thread or user
          self.typeAttachment = typeAttachment # --> type attachment send with message (see <key> at self.dictAttachment)
          self.attachmentID = attachmentID # --> ID of attachment uploaded.
          self.typeChat = typeChat # --> type chat with user/thread (If you want to send to user, let its value be "user". If you want to send to a thread, keep the same value (None))
          self.replyStatus = replyMessage # --> You want to send a message or reply to someone
          self.messageID = messageID # --> ID of message that you need to answer
          
          self.sendMessage(), self.sendRequests()
          return self.results
     
     def attributeValues(self):
     
          for properties in self.properties:
               if self.dataForm.get(properties) is None:
                    self.dataForm[properties] = False
               
     def attachmentCheck(self):
          
          if (self.typeAttachment != None and self.attachmentID != None):
               self.dataForm["has_attachment"] = True
               self.dictItemAttachment = self.dictAttachment[self.typeAttachment]
               if (isinstance(self.attachmentID, list)):
                    for j, idAttach in enumerate(self.attachmentID):
                         self.dataForm[f"{self.dictItemAttachment}[{j}]"] = idAttach
               else:
                    if (isinstance(self.attachmentID, str) or isinstance(self.attachmentID, int)):
                         self.dataForm[f"{self.dictItemAttachment}[0]"] = self.attachmentID
     
     def removeDataAttachmentCheck(self):
     
          if self.dataForm.get('has_attachment'):
               if (isinstance(self.attachmentID, list)):
                    for ij, idAttach in enumerate(self.attachmentID):
                         del self.dataForm[f"{self.dictItemAttachment}[{ij}]"]
                    del self.dataForm["has_attachment"]
                    return
               del self.dataForm[f"{self.dictItemAttachment}[0]"], self.dataForm["has_attachment"]
               return
               
     
     def replyCheck(self):
          
          if (self.replyStatus is None):
               self.dataForm["replied_to_message_id"] = self.messageID
          
          

     def sendMessage(self):
          
          self.dataForm = formAll(self.dataFB, requireGraphql=False)
          
          if (self.typeChat == "user"):
               if (isinstance(self.ID, list)):
                    for i,threadID in enumerate(self.ID):
                         self.dataForm["specific_to_list[" + str(i)+ "]"] = "fbid:" + threadID
                    self.dataForm["specific_to_list[" + str(len(threadID)) + "]"] = "fbid:" + self.dataFB["FacebookID"]
               else:
                    self.dataForm["specific_to_list[0]"] = "fbid:" + self.ID
                    self.dataForm["specific_to_list[1]"] = "fbid:" + self.dataFB["FacebookID"]
                    self.dataForm["other_user_fbid"] = self.ID
          else:
               self.dataForm["thread_fbid"] = self.ID

          self.attributeValues()
          self.dataForm["action_type"] = "ma-type:user-generated-message"
          self.dataForm["client"] = "mercury"
          self.dataForm["body"] = self.content
          self.dataForm["author"] = "fbid:" + self.dataFB["FacebookID"]
          self.dataForm["timestamp"] =  int(time.time() * 1000)
          self.dataForm["timestamp_absolute"] = "Today"
          self.dataForm["source"] = "source:chat:web"
          self.dataForm["source_tags[0]"] = "source:chat"
          self.dataForm["client_thread_id"] = "root:" + gen_threading_id()
          self.dataForm["offline_threading_id"] = gen_threading_id()
          self.dataForm["message_id"] = gen_threading_id()
          self.dataForm["threading_id"] = "<{}:{}-{}@mail.projektitan.com>".format(int(time.time() * 1000), int(random.random() * 4294967295), hex(int(random.random() * 2 ** 31))[2:])
          self.dataForm["ephemeral_ttl_mode"] = "0"
          self.dataForm["manual_retry_cnt"] = "0"
          self.dataForm["ui_push_phase"] = "V3"
          
          self.replyCheck()
          self.attachmentCheck()
          self.sendRequests()
          self.removeDataAttachmentCheck()

     def sendRequests(self):
     
          _main = mainRequests("https://www.facebook.com/messaging/send/", self.dataForm, self.dataFB["cookieFacebook"])
          sendRequests = requests.post(**_main).text
          sendRequests = json.loads(sendRequests.split("for (;;);")[1])
          if sendRequests.get('payload'):
               _ = sendRequests["payload"]["actions"][0]
               self.results = {
                    "success": 1,
                    "payload": {
                         "messageID": _["message_id"],
                         "timestamp": _["timestamp"]
                    }
               }
               return
          self.results = {
               "error": 1,
               "payload": {
                    "error-decription": sendRequests["errorDescription"],
                    "error-code": sendRequests["error"]
               }
          }
          return
          
          # Thread(target=sendRequests, args=()).start()
     

# _ = api()
# dataFB = __facebookToolsV2.dataGetHome('this is Cookie Facebook')
# _.updateDataAndSend(dataFB, "<contents message>", "<userID/threadID>", ...[args])
# test1_sendImage = _.updateDataAndSend(dataFB, "test send image", "100034261636200", typeAttachment="image", attachmentID=757191223105185, typeChat="user", replyMessage=1)
# test2_sendMessage = _.updateDataAndSend(dataFB, "test send msg", "100034261636200", typeChat="user", replyMessage=1)
# print(test1_sendImage)
# print(test2_sendMessage)

#Last updated: 19:02 Wednesday, 13/12/2023