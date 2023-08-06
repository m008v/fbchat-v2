from datetime import datetime
import json, random, requests, attr, time
from threading import Thread
from LorenBot.plugins.utils import Headers, digitToChar, str_base, parse_cookie_string, formAll
     
class api():
     def sendMessage(dataFB, contentSend, threadID, typeAttachment=None, attachmentID=None, typeChat=None, replyMessage=None):
          
          randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
          if (contentSend != None and contentSend != ""):
               if (typeChat == "user"):
                    Host = "m.facebook.com"
                    dataFB["urlPost"] = "https://m.facebook.com/messages/send/"
                    dataForm = formAll(dataFB, requireGraphql=False)
                    dataForm["tids"] = f"cid.c.{threadID}:{dataFB['FacebookID']}"
                    dataForm["body"] = str(contentSend)
                    dataForm["ids[" + threadID + "]"] = threadID
                    dataForm["action_time"] = int(time.time() * 1000)
                    dataForm["waterfall_source"] = "message"
               else:
                    Host = "www.facebook.com"
                    dataFB["urlPost"] = "https://www.facebook.com/messaging/send/"
                    dataForm = formAll(dataFB, requireGraphql=False)
                    dataForm["action_type"] = "ma-type:user-generated-message"
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
                    if (replyMessage == None):
                         dataForm["replied_to_message_id"] = dataFB["messageID"]
                    dataForm["has_attachment"] = True
                    dictAttachment = {
                         "gif": "gif_ids",
                         "image": "image_ids",
                         "video": "video_ids",
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
               
               def sendRequests(dataFB, dataForm):
                    mainRequests = {
                         "headers": Headers(dataFB["cookieFacebook"], dataForm, Host),
                         "timeout": 5,
                         "url": dataFB["urlPost"],
                         "data": dataForm,
                         "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
                         "verify": True
                    }
                         
                    sendRequests = requests.post(**mainRequests).text
                    try: sendRequests = json.loads(sendRequests.split("for (;;);")[1])
                    except: return None
                    
                    # if (str(dataFB["dataUser"]["Contents"]).split(dataFB["prefixBot"])[0] == ""):
                         # for idUser in dataFB["adminList"].items():
                              # contentSendAdmin = "≈ ≈ ≈ ≈ ≈ LorenBot Alert ≈ ≈ ≈ ≈ ≈\n\n🔔Người dùng: " + str(dataFB["dataUser"]["fullName"]) + " (ID: " + str(dataFB["dataUser"]["IDUser"]) + ") đã dùng bot.\n📋Tin nhắn của người dùng: " + str(dataFB["dataUser"]["Contents"]) + "\n⏰Thời gian: " + str(datetime.today())
                              # api.sendMessage(dataFB, contentSendAdmin, idUser[0], typeChat="user")
                    
                    try:                                                   
                         if (sendRequests.get("error") != None):
                              return print("\033[1;97mĐã xảy ra lỗi: " + str({
                                   "errorCode": sendRequests["error"],
                                   "errorSummary": sendRequests["errorSummary"],
                                   "errorDescription": sendRequests["errorDescription"]
                              }))
                         else: 
                              return {
                                   "threadID": sendRequests["payload"]["actions"][0]["thread_fbid"],
                                   "messageID": sendRequests["payload"]["actions"][0]["message_id"],
                                   "timeStamps": sendRequests["payload"]["actions"][0]["timestamp"]
                              }
                    except:
                         return None
               Thread(target=sendRequests, args=(dataFB, dataForm)).start()
     

""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):

     -setCookies: Cookie account Facebook
     - dataFB: lấy từ __facebookToolsV2.dataGetHome(setCookies)
     - contentSend: nội dung tin nhắn
     - threadID: ID nhóm cần gửi tin nhắn
     - typeAttachment: chọn loại tệp- đính kèm cần gửi (image, video, gif, file.....)
     - attachmentID: ID tệp đính kèm đã được upload lên từ __uploadImages (có thể dùng list để gửi nhiều Attachment cùng lúc. VD: [45647...., 5443754....., 54492115.....])
     - typeChat: "user" => gửi tin nhắn cho người dùng Facebook, None => gửi tin nhắn cho Thread
     - replyMessage: None => sẽ reply tin nhắn gần nhất, False => Không reply, sẽ chỉ gửi tin nhắn

* Kết quả trả về:

     - khi gửi tin nhắn thành công: 
          {'threadID': '4805171782880318', 'messageID': 'mid.$gABESRz00DD6PA6t1pGI0mYsQ8FpX', 'timeStamps': 1687157091748}
     - khi gửi tin nhắn thất bại:
          {'errorCode': 1545003, 'errorSummary': 'Hành động không hợp lệ', 'errorDescription': 'Bạn không thể thực hiện hành động đó.'}
     
     - Ghi chú: tùy thuộc vào nhiều trường hợp mà error có thể báo code lỗi và chi tiết khác nhau!

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 13:53 ngày 19/6/2023 • Cập nhật mới nhất: 7:43 20/7/2023
✓Tôn trọng tác giả ❤️
"""
