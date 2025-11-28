FBChat-Remake: Open Source
=======================================
 Chào người dùng thân mến, tôi đã quay trở lại sau khoảng thời gian dài vắng bóng. Hiện tại dự án sẽ dần được sửa chữa các lỗi do người dùng và cập nhật thêm các tính năng dần. Xin cảm ơn tất cả vì thời gian qua đã gửi báo cáo đén tôi. (Lúc 19/08/2025)
**📢THÔNG BÁO QUAN TRỌNG:** Kể từ 11/2024, Facebook đã chính thức mã hóa tin nhắn đàu cuối giữa người dùng với nhau (*End-to-End Encryption (E2EE)*). Chính vì thế, bây giờ thư viện chỉ lấy được tin nhắn trong nhóm, **không thể** lấy được tin nhắn giữa các người dùng với nhau.

- - - - - - - - -

Xin chào, tôi là **MinhHuyDev**. Lời nói đầu, đây là lần đầu tiên mà mình làm lại một source lớn như vậy nên sẽ không tránh được những *sai sót* trong quá trình code, rất mong sẽ được người dùng báo cáo lại **Lỗi** tại issues của GitHub này nhé:3

***** *Đây không phải là API chính thức;* Facebook có sẵn API dành cho chatbot `tại đây <https://developers.facebook.com/docs/messenger-platform/>`_. Thư viện này khác ở chỗ nó sử dụng tài khoản/cookie Facebook thông thường để thay thế.

.. image:: https://i.ibb.co/3TWntY6/Picsart-23-08-12-15-11-30-693.jpg

**👽Bạn không thể hiểu được tiếng Việt?**, bạn có thể đọc **README** (*ENGLISH*):  `tại đây <https://github.com/MinhHuyDev/fbchat-v2/blob/main/README_EN.rst>`_

**📢Dành cho người mới**: *Lướt xuống cuối trang bạn sẽ thấy* **TUTORIAL (Hướng dẫn)** *nhận tin nhắn và gửi tin nhắn nhé!*

=======================================
Thông tin cơ bản
=======================================

- **Được làm lại từ:** `𝘧𝘣𝘤𝘩𝘢𝘵 (𝘗𝘺𝘵𝘩𝘰𝘯) <https://fbchat.readthedocs.io/en/stable/>`_
- **Ngôn ngữ lập trình:** `𝘗𝘺𝘵𝘩𝘰𝘯 <https://www.python.org/>`_
- **Phát triển bởi:** *Nguyễn Minh Huy*

=======================================
Có gì mới trong phiên bản này?
=======================================

**NEW**: Sửa lỗi một vài thứ và CLEAR CODE gọn hơn

=======================================
Tutorial (Hướng dẫn cơ bản)
=======================================

**Đầu tiên**: Người dùng cần phải cài đặt *tất cả* các gói tài nguyên cần thiết để có thể sử dụng. Nếu bạn chưa cài đặt, hãy dùng lệnh sau:

.. code-block:: bash

  git clone https://github.com/MinhHuyDev/fbchat-v2

**Tiếp theo**: Hãy tạo thư mục trong chính folder mà mình vừa tải về từ *GitHub* về bằng cách sau:

*Đối với* **Windows (Command Prompt/PowerShell):**

.. code-block:: bash
  
  cd fbchat-v2/src && type nul > mainBot.py

*Đối với* **Mac/Linux:**

.. code-block:: bash
  
  cd fbchat-v2/src && touch mainBot.py

**Sau đó**: Tiếp tục vào file **mainBot.py**, Và copy đoạn code sau và dán vào file:

.. code-block:: python

     from __facebookToolsV2 import dataGetHome, fbTools
     from __messageListenV2 import listeningEvent  # Import the specific class or module you need
     from __sendMessage import api
     import datetime, threading, os, json
     
     class fbClient:
         def __init__(self, cookies, dataFB):
             self.cookies = cookies
             self.dataFB = dataFB
             self.messageID = None
             self.prefix = "/" # This is the command prompt; when you enter this symbol, the corresponding command will be invoked. Additionally, you can customize it as per your preference (e.g., , . * ! ? etc)
             self.pathFile = ".mqttMessage"
             self.recentReceivedMessages = []
     
         def setDefaultValue(self):
             self.userID, self.bodyMessage, self.replyToID, self.bodySend, self.commandPlugins = [None] * 5
     
         def receiveCommandAndSend(self):
             if (self.dataFB["FacebookID"] != self.userID):
                  match self.commandPlugins.lower():
                      case "uptime":
                          self.bodySend = "datetime: " + str(datetime.datetime.now())
                      case "hola" | "hello" | "hi":
                          self.bodySend = "Hey,", self.userID
                      case "ping":
                          self.bodySend = "Pong!"
                      case __:
                          self.bodySend = self.bodyMessage
                  mainSend = api()  # Use the specific class or module you imported
                  threading.Thread(target=mainSend.send, args=(self.dataFB, self.bodySend, self.replyToID)).start()
                  self.setDefaultValue()
     
         def prefixCheck(self):
             if self.bodyMessage[0] == self.prefix:
                 self.commandPlugins = self.bodyMessage.split(',')[1]
             else:
                 self.commandPlugins = self.bodyMessage
               
     
         def receiveMessage(self):
             self.fbt = fbTools(self.dataFB, 0)
             mainReceiveMessage = listeningEvent(self.fbt, self.dataFB)  # Use the specific class or module you imported
             mainReceiveMessage.get_last_seq_id()
             threading.Thread(target=mainReceiveMessage.connect_mqtt, args=()).start()
             """
             Why am I using Threading here? 
             Because when calling connect_mqtt(), the programs after it won't be able to run 
             as it continuously connects to the Facebook server. To overcome this, I've used threading 
             to make it run concurrently with other functions!
             """
             while 1:
                if os.path.isfile(self.pathFile):
                    try:
                        self.bodyMain = json.loads(open(self.pathFile, "r", encoding="utf-8").read())
                        # print(f"{self.bodyMain['messageID']} != {self.messageID} {self.bodyMain['messageID'] != self.messageID}")
                        if self.bodyMain['messageID'] != self.messageID:
                            self.userID = self.bodyMain['userID']
                            self.messageID = self.bodyMain['messageID']
                            self.bodyMessage = self.bodyMain['body']
                            self.replyToID = self.bodyMain['replyToID']
                            print(f"> userID: {self.userID}\n> messageID: {self.messageID}\n> messageContents: {self.bodyMessage}\n> From {self.bodyMain['type']}ID: {self.replyToID}\n- - - - -")
                            self.prefixCheck()
                            self.receiveCommandAndSend()
                            self.setDefaultValue()
                    except:
                        pass
     
     cookies = "this is set Cookie Facebook"
     dataFB = dataGetHome(cookies)
     _ = fbClient(cookies, dataFB)
     _.setDefaultValue()
     _.receiveMessage()
     print("done!")
     
**🖇️LƯU Ý:** Đây chỉ là một bản code mẫu về nhận tin nhắn và gửi tin nhắn, Nếu xảy ra lỗi. Hãy đóng góp bằng cách sửa nó và gửi thông tin lỗi vào *issue* hoặc hãy liên hệ trực tiếp với tôi qua **Telegram**
     
Sau đó, quay lại **Terminal/CMD** và chạy file này bằng lệnh sau:

.. code-block:: bash

 python mainBot.py

Nếu xảy ra lỗi và không chạy được, hãy thử lại bằng hai lệnh sau:

.. code-block:: bash

 python3 mainBot.py

hoặc

.. code-block:: bash

 py mainBot.py

💔Nếu vẫn xảy ra lỗi. Vui lòng kiểm tra xem đã tải Python về thiết bị hay chưa. Nếu chưa tải, hãy nhấp `vào đây <https://www.python.org/downloads/>`_ để được chuyển đến trang tải Python chính thức.

**🏅Dưới đây là hình ảnh khi chạy được bot thành công**:

.. image:: https://i.ibb.co/pdbBTWz/nh-ch-p-m-n-h-nh-2024-01-30-130047.png

====================

.. image:: https://i.ibb.co/fvJq87Z/Screenshot-2023-08-18-20-25-51-435-com-offsec-nethunter-kex.png

🫶🏻Cảm ơn bạn đã đọc đến đây! Nếu bạn vẫn còn **nhiều câu hỏi thắc mắc**. Hãy lướt xuống dưới để tìm **câu trả lời** cho riêng mình nhé :3 Yêuuuuuu

=======================================
Các câu hỏi thường gặp
=======================================

Bạn có thể xem các vấn đề thường gặp hoặc Tutorial tại đây: `DOCS.md <https://github.com/MinhHuyDev/fbchat-v2/blob/main/DOCS.md>`_

=======================================
Thông báo về phiên bản mới
=======================================

*📢*: Coming soon...

=======================================
Thông tin liên hệ
=======================================

- **Facebook:** `Nguyễn Minh Huy :( !! <https://www.facebook.com/Booking.MinhHuyDev>`_
- **Telegram:** `MinhHuyDev <https://t.me/MinhHuyDev>`_
- **Website**: `mhuyz.dev <https://mhuyz.dev>`_
