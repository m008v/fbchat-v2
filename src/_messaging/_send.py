from __future__ import annotations

import json, random, time
from typing import Any
from _core._utils import gen_threading_id, mainRequests, formAll, send_request, send_request_async
     
class api:
     
     def __init__(self) -> None:
     
          self.dataFB: dict[str, Any] | None
          self.content: str | None
          self.ID: str | list[str] | None
          self.typeAttachment: str | None
          self.attachmentID: str | int | list[str | int] | None
          self.typeChat: str | None
          self.replyStatus: bool | None
          self.messageID: str | None
          self.dataFB, self.content, self.ID, self.typeAttachment, self.attachmentID, self.typeChat, self.replyStatus, self.messageID = [None] * 8
          self.properties: list[str] = ["is_unread", "is_cleared", "is_forward", "is_filtered_content", "is_filtered_content_bh", "is_filtered_content_account", "is_filtered_content_quasar", "is_filtered_content_invalid_app", "is_spoof_warning"]
          self.dictAttachment: dict[str | None, str] = {
               # key: value
               "gif": "gif_ids",
               "image": "image_ids",
               "video": "video_ids",
               "file": "file_ids",
               "audio": "audio_ids",
               None: "this is not a Attachment we requested, try again later (đây không phải là Tệp đính kèm mà chúng tôi đã yêu cầu, hãy thử lại sau)"
          }
          self.results: dict[str, Any] = {}
          self.dataForm: dict[str, Any] = {}
          self.dictItemAttachment: str = ""
          
          
     def send(self, dataFB: dict[str, Any], contentSend: str | int, threadID: str | list[str], typeAttachment: str | None = None, attachmentID: str | int | list[str | int] | None = None, typeChat: str | None = None, replyMessage: bool | None = None, messageID: str | None = None) -> dict[str, Any]:
          
          self.dataFB = dataFB # --> data from home Facebook
          self.content = str(contentSend) # --> contents message
          self.ID = threadID # --> ID of thread or user
          self.typeAttachment = typeAttachment # --> type attachment send with message (see <key> at self.dictAttachment)
          self.attachmentID = attachmentID # --> ID of attachment uploaded.
          self.typeChat = typeChat # --> type chat with user/thread (If you want to send to user, let its value be "user". If you want to send to a thread, keep the same value (None))
          self.replyStatus = replyMessage # --> You want to send a message or reply to someone = Set "true" and set messageID. If you want to send a message normally, keep the same value (None)
          self.messageID = messageID
          
          self.sendMessage()
          self.removeValueToInputed()
          
          return self.results
          
     async def send_async(self, dataFB: dict[str, Any], contentSend: str | int, threadID: str | list[str], typeAttachment: str | None = None, attachmentID: str | int | list[str | int] | None = None, typeChat: str | None = None, replyMessage: bool | None = None, messageID: str | None = None) -> dict[str, Any]:
          self.dataFB = dataFB
          self.content = str(contentSend)
          self.ID = threadID
          self.typeAttachment = typeAttachment
          self.attachmentID = attachmentID
          self.typeChat = typeChat
          self.replyStatus = replyMessage
          self.messageID = messageID
          
          await self.sendMessage_async()
          self.removeValueToInputed()
          
          return self.results
     
     def removeValueToInputed(self) -> None:
          self.typeAttachment, self.attachmentID, self.typeChat, self.replyStatus, self.messageID = [None] * 5
     
     def attributeValues(self) -> None:
     
          for properties in self.properties:
               if self.dataForm.get(properties) is None:
                    self.dataForm[properties] = False
               
     def attachmentCheck(self) -> None:
          
          if (self.typeAttachment != None and self.attachmentID != None):
               self.dataForm["has_attachment"] = True
               self.dictItemAttachment = self.dictAttachment[self.typeAttachment]
               if (isinstance(self.attachmentID, list)):
                    for j, idAttach in enumerate(self.attachmentID):
                         self.dataForm[f"{self.dictItemAttachment}[{j}]"] = idAttach
               else:
                    if (isinstance(self.attachmentID, str) or isinstance(self.attachmentID, int)):
                         self.dataForm[f"{self.dictItemAttachment}[0]"] = self.attachmentID
     
     def removeDataAttachmentCheck(self) -> None:
     
          if self.dataForm.get('has_attachment'):
               if (isinstance(self.attachmentID, list)):
                    for ij, idAttach in enumerate(self.attachmentID):
                         del self.dataForm[f"{self.dictItemAttachment}[{ij}]"]
                    del self.dataForm["has_attachment"]
                    return
               del self.dataForm[f"{self.dictItemAttachment}[0]"], self.dataForm["has_attachment"]
               return
               
     
     def replyCheck(self) -> None:
          
          if (self.replyStatus is True and self.messageID != None):
               self.dataForm["replied_to_message_id"] = self.messageID
          
          

     def sendMessage(self) -> None:
          
          self.dataForm = formAll(self.dataFB, requireGraphql=False)
          
          self.attributeValues()
          
          self.dataForm["action_type"] = "ma-type:user-generated-message"
          self.dataForm["timestamp"] = int(time.time() * 1000)
          self.dataForm["source"] = "source:chat:web"
          
          if (self.typeChat == "user"):
               if (isinstance(self.ID, str) or isinstance(self.ID, int)):
                    self.dataForm["specific_to_list[0]"] = "fbid:" + str(self.ID)
                    self.dataForm["specific_to_list[1]"] = "fbid:" + str(self.dataFB["FacebookID"])
                    self.dataForm["other_user_fbid"] = self.ID
               elif isinstance(self.ID, list):
                    for i in range(len(self.ID)):
                         self.dataForm[f"specific_to_list[{i}]"] = "fbid:" + str(self.ID[i])
                    self.dataForm[f"specific_to_list[{len(self.ID)}]"] = "fbid:" + str(self.dataFB["FacebookID"])
          else:
               self.dataForm["thread_fbid"] = self.ID
          
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

     async def sendMessage_async(self) -> None:
          self.dataForm = formAll(self.dataFB, requireGraphql=False)
          self.attributeValues()
          self.dataForm["action_type"] = "ma-type:user-generated-message"
          self.dataForm["timestamp"] = int(time.time() * 1000)
          self.dataForm["source"] = "source:chat:web"
          if (self.typeChat == "user"):
               if (isinstance(self.ID, str) or isinstance(self.ID, int)):
                    self.dataForm["specific_to_list[0]"] = "fbid:" + str(self.ID)
                    self.dataForm["specific_to_list[1]"] = "fbid:" + str(self.dataFB["FacebookID"])
                    self.dataForm["other_user_fbid"] = self.ID
               elif isinstance(self.ID, list):
                    for i in range(len(self.ID)):
                         self.dataForm[f"specific_to_list[{i}]"] = "fbid:" + str(self.ID[i])
                    self.dataForm[f"specific_to_list[{len(self.ID)}]"] = "fbid:" + str(self.dataFB["FacebookID"])
          else:
               self.dataForm["thread_fbid"] = self.ID
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
          await self.sendRequests_async()
          self.removeDataAttachmentCheck()

     def _parse_response(self, text: str) -> None:
          if text.startswith("for (;;);"):
               text = text.split("for (;;);", 1)[1]
               
          try:
               sendRequests = json.loads(text)
          except (ValueError, json.JSONDecodeError):
               self.results = {
                    "error": 1,
                    "payload": {
                         "error-decription": "Invalid JSON response from server.",
                         "raw": text[:300]
                    }
               }
               return

          if sendRequests.get('payload'):
               payload_data = sendRequests["payload"]
               if "actions" in payload_data and len(payload_data["actions"]) > 0:
                    _ = payload_data["actions"][0]
                    self.results = {
                         "success": 1,
                         "payload": {
                              "messageID": _["message_id"],
                              "timestamp": _["timestamp"]
                         }
                    }
                    return
               else:
                    self.results = {
                         "error": 1,
                         "payload": {
                              "error-decription": "Payload does not contain 'actions'.",
                              "raw": sendRequests
                         }
                    }
                    return
          self.results = {
               "error": 1,
               "payload": {
                    "error-decription": sendRequests.get("errorDescription"),
                    "error-code": sendRequests.get("error"),
                    "raw": sendRequests
               }
          }
          return

     def sendRequests(self) -> None:
          _main = mainRequests("https://www.facebook.com/messaging/send/", self.dataForm, self.dataFB["cookieFacebook"])
          res = send_request(_main)
          self._parse_response(res.text)

     async def sendRequests_async(self) -> None:
          _main = mainRequests("https://www.facebook.com/messaging/send/", self.dataForm, self.dataFB["cookieFacebook"])
          res = await send_request_async(_main)
          self._parse_response(res.text)
     

# _ = api()
# from _core._session import dataGetHome
# dataFB = dataGetHome('this is cookie Facebook')
# _.send(dataFB, "<contents message>", "<userID/threadID>", ...[args])
# test1_sendImage = _.send(dataFB, "test send image", "100034261636200", typeAttachment="image", attachmentID=757191223105185, typeChat="user", replyMessage=1)
# test2_sendMessage = _.send(dataFB, "test send msg", "100034261636200", typeChat="user", replyMessage=1)
# print(test1_sendImage)
# print(test2_sendMessage)

#Last updated: 23:07 Friday, 13/12/2023
