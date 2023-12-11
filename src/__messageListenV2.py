from requests import Response
import json
import ssl
import time
import string
import attr
import random
import paho.mqtt.client as mqtt
import __facebookToolsV2
from urllib.parse import urlparse
from utils import generate_session_id, generate_client_id, json_minimal, _set_chat_on

"""
Lời đầu tiên, xin cảm ơn tất cả user của fbchat-v2 vừa qua đã đóng góp cho dự án
Và bây giờ bạn có thể dùng wss (websocket) nhận tin nhắn thay vì requests
Tôi đã remake lại chúng, khi được sự ủng hộ của các user! Thanks for all.
Author: MinhHuyDev
Date: 23:28 Sunday, 10/12/2023
"""

     
class listeningEvent:
     _on_message = attr.ib()
     def __init__(self, fbt, dataFB):
          self.bodyResults = {
               "body": None, # Nội dung tin nhắn - content message
               "timestamp": 0, # Thời gian tin nhắn được gửi - The time the message was sent
               "userID": 0, # Người gửi tin nhắn - Author sent message
               "messageID": None, # ID tin nhắn - MessageID
               "replyToID": 0, # Nơi gửi và nơi nhận lại tin nhắn cần phản hồi - Where to send and receive the message that needs response
               "type": None, # user/thread
               "attachments": { # Tệp đính kèm được gửi - Attachment sent
                    "id": 0, # id attachment
                    "url": None, # url attachment
               }
          }
          self.syncToken = None
          self.lastSeqID = None
          self.dataFB = dataFB
          self.fbt = fbt
     
     
     def get_last_seq_id(self):
          self.fbt.getAllThreadList()
          self.lastSeqID = self.fbt.last_seq_id
          print(f"last_seq_id: {self.lastSeqID}")
          return 
               
     def connect_mqtt(self):
          
          chat_on: bool = json_minimal(True)
          session_id = generate_session_id()
          user = {
               "u": self.dataFB["FacebookID"],
               "s": session_id,
               "chat_on": chat_on,
               "fg": False,
               "d": generate_client_id(),
               "ct": "websocket",
               "aid": 219994525426954,
               "mqtt_sid": "",
               "cp": 3,
               "ecp": 10,
               "st": "/t_ms",
               "pm": [],
               "dc": "",
               "no_auto_fg": True,
               "gas": None,
               "pack": [],
          }
          
          host = f"wss://edge-chat.facebook.com/chat?region=eag&sid={session_id}"
          options = {
               "client_id": "mqttwsclient",
               "username": json_minimal(user),
               "clean": True,
               "ws_options": {
                     "headers": {
                         "Cookie": self.dataFB['cookieFacebook'],
                         "Origin": "https://www.facebook.com",
                         "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
                         "Referer": "https://www.facebook.com/",
                         "Host": "edge-chat.facebook.com",
                     },
               },
               "keepalive": 10,
          }
          
                    
          def _messenger_queue_publish(client: mqtt.Client, userdata, flags, rc):
               topics = None
                
               queue = {
                    "sync_api_version": 10,
                    "max_deltas_able_to_process": 1000,
                    "delta_batch_size": 500,
                    "encoding": "JSON",
                    "entity_fbid": self.dataFB['FacebookID']
               }
               
               if (self.syncToken == None):
                    topics = "/messenger_sync_create_queue"
                    queue["initial_titan_sequence_id"] = self.lastSeqID
                    queue["device_params"] = None
               else:
                    topics = "/messenger_sync_get_diffs"
                    queue["last_seq_id"] = self.lastSeqID
                    queue["sync_token"] = "1"
               
               client.publish(
                    topics,
                    json_minimal(queue),
                    qos=1,
                    retain=False,
               )
     
               
          def on_message(client, userdata, msg):
               try:
                    j = json.loads(msg.payload.decode())
                    if j.get('deltas') is not None:
                         _ = j["deltas"][0]
                         if _.get('messageMetadata') is not None:
                              self.bodyResults["body"] = _.get("body")
                              self.bodyResults["timestamp"] = _["messageMetadata"]["timestamp"]
                              self.bodyResults["userID"] = _["messageMetadata"]["actorFbId"]
                              self.bodyResults["messageID"] = _["messageMetadata"]["messageId"]
                              self.bodyResults["replyToID"] = _["messageMetadata"]["threadKey"].get("otherUserFbId") if _["messageMetadata"]["threadKey"].get("otherUserFbId") is not None else _["messageMetadata"]["threadKey"].get("threadFbId")
                              self.bodyResults["type"] = "user" if _["messageMetadata"]["threadKey"].get("otherUserFbId") is not None else "thread"
                              if len(_["attachments"]) > 0:
                                   try:
                                        self.bodyResults["attachments"]["id"] = _["attachments"][0]["fbid"]
                                        self.bodyResults["attachments"]["url"] = _["attachments"][0]["mercury"]["blob_attachment"]["preview"]["uri"]
                                   except:   
                                        self.bodyResults["attachments"]["id"] = "This is image_url!?"
                              print(self.bodyResults)
                              # Bạn có thể dùng các tệp tin hoặc socket để truyền dữ liệu qua các file plugins khác / main của bot
                              # You can use files or socket to transfer data to other plugins files / main of the bot
                              """Example:
                                   Đơn giản, hãy dùng file, simply use file:
                                   - Hãy tạo 1 file tại vị trí này, với tên bạn đặt và ghi nội dung trong bodyResults vào trong tệp đó
                                   - Bên file được truyền, hãy kiểm tra xem file có tồn tại hay không bằng if else với os
                                   - Nếu tồn tại, hãy json.loads() file đó và lấy dữ liệu đó ra
                                   ≈ ≈ ≈ ≈
                                   - tại file này:
                                        open(".content.json", "w").write(json.dumps(self.bodyResults, indent=5))
                                   - tại file được truyền:
                                        import os 
                                        ìt (os.path.isfile(".content.json")):
                                             print("tìm thấy dữ liệu")
                                             # bắt đầu json.loads() và lấy dữ liệu ra
                              """
                    if "syncToken" in j and "firstDeltaSeqId" in j:
                         self.syncToken = j["syncToken"]
                         self.lastSeqID = j["firstDeltaSeqId"]
                         return
                    if "lastIssuedSeqId" in j:
                         self.lastSeqID = j["lastIssuedSeqId"]
                    if "errorCode" in j:
                         error = j["errorCode"]
                         print(f"ERR {err}")
                         # ERROR_QUEUE_NOT_FOUND means that the queue was deleted, since too
                         # much time passed, or that it was simply missing
                         # ERROR_QUEUE_OVERFLOW means that the sequence id was too small, so
                         # the desired events could not be retrieved
                         self.syncToken = None
                         self.get_last_seq_id() # update self.lastSeqID
                         self._messenger_queue_publish()
               except (UnicodeDecodeError):
                    print("ERR Failed parsing MQTT data on /t_ms as JSON")
               
          def on_disconnect(client, userdata, rc):
                 print("Disconnected?")
     
          self.mqtt = mqtt.Client(
               client_id=options["client_id"],
               clean_session=options["clean"],
               protocol=mqtt.MQTTv31,
               transport="websockets",
          )
          
          self.mqtt.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
          
          self.mqtt.on_connect = _messenger_queue_publish
          self.mqtt.on_message = on_message
          self.mqtt.on_disconnect = on_disconnect
          
          self.mqtt.username_pw_set(username=options["username"])
          parsed_host = urlparse(host)
          
          self.mqtt.ws_set_options(
               path=f"{parsed_host.path}?{parsed_host.query}",
               headers=options["ws_options"]["headers"],
          )
          
          # connect
          self.mqtt.connect(
               host=options["ws_options"]["headers"]["Host"],
               port=443,
               keepalive=options["keepalive"],
          )
          self.mqtt.loop_forever()
          
"""
# This is example code:
i = __facebookToolsV2.dataGetHome('cookie Facebook')
fbt = __facebookToolsV2.fbTools(i, 0)
_ = listeningEvent(fbt, i)
_.get_last_seq_id()
_.connect_mqtt()
"""
# last updated: 21:18 Monday, 11/12/2023