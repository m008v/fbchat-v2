import json
import ssl
import time
import datetime
import attr
import paho.mqtt.client as mqtt
from urllib.parse import urlparse
from _core._utils import generate_session_id, generate_client_id, json_minimal
from _features._thread import *
"""
Lời đầu tiên, xin cảm ơn tất cả user của fbchat-v2 vừa qua đã đóng góp cho dự án
Và bây giờ bạn có thể dùng wss (websocket) nhận tin nhắn thay vì requests
Tôi đã remake lại chúng, khi được sự ủng hộ của các user! Thanks for all.
Author: MinhHuyDev
Date: 23:28 Sunday, 10/12/2023
"""

     
class listeningEvent:
     _on_message = attr.ib()
     def __init__(self, dataFB):
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
          try:
               self.fbt = _all_thread_data.func(dataFB)
          except Exception as err:
               print(f"[{datetime.datetime.now()}]failed initial thread data fetch: {err}")
               self.fbt = {}


     def _coerce_seq_id(self, value, source="seq_id"):
          try:
               seq_id = int(str(value).strip())
          except (TypeError, ValueError):
               print(f"[{datetime.datetime.now()}]ignore invalid {source}: {value}")
               return None

          if seq_id < 0:
               print(f"[{datetime.datetime.now()}]ignore invalid negative {source}: {seq_id}")
               return None
          return seq_id

     def _set_last_seq_id(self, value, source="seq_id", allow_reset=False):
          seq_id = self._coerce_seq_id(value, source)
          if seq_id is None:
               return False

          previous = self._coerce_seq_id(self.lastSeqID, "previous last_seq_id") if self.lastSeqID is not None else None
          if previous is not None and seq_id < previous and not allow_reset:
               print(f"[{datetime.datetime.now()}]ignore stale {source}: {seq_id} < {previous}")
               return False

          self.lastSeqID = seq_id
          return True
     
     
     def get_last_seq_id(self):
          previousSeqID = self.lastSeqID
          try:
               self.fbt = _all_thread_data.func(self.dataFB)
               nextSeqID = self.fbt.get("last_seq_id")
               if self._set_last_seq_id(nextSeqID, "graphql sync_sequence_id", allow_reset=True):
                    pass
               elif previousSeqID is not None:
                    print(f"[{datetime.datetime.now()}]last_seq_id unavailable, keep previous: {previousSeqID}")
                    self.lastSeqID = previousSeqID
               else:
                    self.lastSeqID = None
          except Exception as err:
               if previousSeqID is not None:
                    print(f"[{datetime.datetime.now()}]failed refreshing last_seq_id, keep previous: {err}")
                    self.lastSeqID = previousSeqID
               else:
                    print(f"[{datetime.datetime.now()}]failed refreshing last_seq_id: {err}")
                    self.lastSeqID = None
          print(f"[{datetime.datetime.now()}]last_seq_id: {self.lastSeqID}")
          return 
               
     def connect_mqtt(self):
          # Thêm retry counter
          self.retry_count = 0
          self.max_retries = 3
          
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
               # GraphQL sync_sequence_id chỉ dùng để tạo queue mới.
               # Khi đã có syncToken, lastSeqID phải đi theo MQTT lastIssuedSeqId/firstDeltaSeqId.
               if self.syncToken is None:
                    self.get_last_seq_id()
               elif self.lastSeqID is None:
                    print("syncToken exists but last_seq_id is missing; recreate Messenger sync queue.")
                    self.syncToken = None
                    self.get_last_seq_id()
               if self.lastSeqID is None:
                    print("ERR last_seq_id is None; cannot create Messenger sync queue. Refresh Facebook cookie and restart.")
                    client.disconnect()
                    return
               
               topics = None
               queue = {
                    "sync_api_version": 10,
                    "max_deltas_able_to_process": 1000,
                    "delta_batch_size": 500,
                    "encoding": "JSON",
                    "entity_fbid": self.dataFB['FacebookID'],
                    "orca_version": "1.2.0" 
               }
               
               if self.syncToken is None:
                    topics = "/messenger_sync_create_queue"
                    queue["initial_titan_sequence_id"] = self.lastSeqID
                    queue["device_params"] = None
               else:
                    topics = "/messenger_sync_get_diffs"
                    queue["last_seq_id"] = self.lastSeqID
                    queue["sync_token"] = self.syncToken  
               print(f"Publishing to {topics} with seq_id: {self.lastSeqID}")  # Debug
               
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
                                   except (KeyError, TypeError, IndexError):
                                        self.bodyResults["attachments"]["id"] = "Unable to retrieve attachment ID"
                    if "syncToken" in j and "firstDeltaSeqId" in j:
                         self.syncToken = j["syncToken"]
                         self._set_last_seq_id(j.get("lastIssuedSeqId") or j.get("firstDeltaSeqId"), "mqtt first/last seq_id")
                         self.retry_count = 0
                         return
                    if "lastIssuedSeqId" in j:
                         self._set_last_seq_id(j["lastIssuedSeqId"], "mqtt lastIssuedSeqId")
                    if "errorCode" in j:
                         error = j["errorCode"]
                         print(f"ERR {error}")
                         
                         is_queue_overflow = error == 100 or str(error).upper() == "ERROR_QUEUE_OVERFLOW"
                         if is_queue_overflow:  # ERROR_QUEUE_OVERFLOW
                              print("Queue overflow - resetting and retrying...")
                              self.syncToken = None
                              self.retry_count += 1

                              self.get_last_seq_id()  # Fresh seq ID
                              if self.lastSeqID is None:
                                   print("Cannot recover queue: last_seq_id is still None. Refresh Facebook cookie and restart.")
                                   self.mqtt.disconnect()
                                   return
                              if self.retry_count > self.max_retries:
                                   print("Max queue-overflow retries reached - full reconnect")
                                   self.retry_count = 0
                                   self.mqtt.disconnect()
                                   time.sleep(10)
                                   self.connect_mqtt()
                                   return

                              queue = {
                                   "sync_api_version": 10,
                                   "max_deltas_able_to_process": 1000,
                                   "delta_batch_size": 500,
                                   "encoding": "JSON",
                                   "entity_fbid": self.dataFB['FacebookID'],
                                   "initial_titan_sequence_id": self.lastSeqID,
                                   "device_params": None,
                                   "orca_version": "1.2.0"
                              }
                              print(f"Publishing to /messenger_sync_create_queue with seq_id: {self.lastSeqID}")
                              client.publish(
                                   "/messenger_sync_create_queue",
                                   json_minimal(queue),
                                   qos=1,
                                   retain=False,
                              )
                         else:
                            print("Max retries reached - full reconnect")
                            self.retry_count = 0
                            self.mqtt.disconnect()
                            time.sleep(10)  # Delay trước reconnect
                            self.connect_mqtt()  # Reconnect full (regenerate session)
                          
                         return  # Dừng xử lý error
               
               except (UnicodeDecodeError):
                    print("ERR Failed parsing MQTT data on /t_ms as JSON")
               
          def on_disconnect(client, userdata, rc):
                 print("Disconnected with result code " + str(rc))
                 if rc != 0:  # Không phải disconnect bình thường
                      print("Unexpected disconnect - reconnecting in 10s...")
                      time.sleep(10)
                      self.connect_mqtt()  # Tự reconnect
     
          def on_subscribe(client, userdata, mid, granted_qos):
                 print("Subscribed: " + str(mid) + " " + str(granted_qos))
     
          def on_unsubscribe(client, userdata, mid):
                 print("Unsubscribed: " + str(mid))
     
          def on_log(client, userdata, level, buf):
                 print("Log: " + str(buf))
            
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
          self.mqtt.on_subscribe = on_subscribe
          self.mqtt.on_unsubscribe = on_unsubscribe
          
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
from _core._session import dataGetHome
from _messaging._listening import listeningEvent

dataFB = dataGetHome('cookie Facebook')
_ = listeningEvent(dataFB)
_.get_last_seq_id()
_.connect_mqtt()
"""
# last updated: 00:04 20/03/2026
