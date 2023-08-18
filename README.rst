FBChat-Remake: Open Source
=======================================

Xin chào, tôi là **MinhHuyDev**. Lời nói đầu, đây là lần đầu tiên mà mình làm lại một source lớn như vậy nên sẽ không tránh được những *sai sót* trong quá trình code, rất mong sẽ được người dùng báo cáo lại **Lỗi** tại issues của GitHub này nhé:3

.. image:: https://i.ibb.co/3TWntY6/Picsart-23-08-12-15-11-30-693.jpg

**📢Dành cho người mới**: *Lướt xuống cuối trang bạn sẽ thấy* **TUTORIAL (Hướng dẫn)** *nhận tin nhắn và gửi tin nhắn nhé!*

=======================================
Thông tin cơ bản về FBChat Remake
=======================================

- **Được làm lại từ:** `𝘧𝘣𝘤𝘩𝘢𝘵 (𝘗𝘺𝘵𝘩𝘰𝘯) <https://fbchat.readthedocs.io/en/stable/>`_
- **Người đóng góp**: *hakuOwO*
- **Ngôn ngữ lập trình:** `𝘗𝘺𝘵𝘩𝘰𝘯 <https://www.python.org/>`_
- **Phát triển bởi:** *Nguyễn Minh Huy*
- **Phiên bản hiện tại:** *1.0.3.1*
- **Cập nhật lần cuối:** *16:07 12/08/2023*
- **Vùng thời gian**: *GMT + 07*

=======================================
Tutorial (Hướng dẫn)
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

     from __facebookToolsV2 import dataGetHome
     from __messageListen import Listen
     from __sendMessage import *
     import datetime
     
     class fbchatClient: # initialize client
     
          def __init__(self, setCookies, threadID): 
               self.cookies = setCookies
               self.threadID = threadID
          
          def getData(self): # Get value fb_dtsg, jazoest and more...
               try: self.dataFB = dataGetHome(self.cookies)
               except: return 0
          
          def messageListen(self):
               _ = Listen(self.dataFB, self.threadID)
               try: return _.get('results')
               except: pass
               
          def sendMsg(self, contentSend):
               _ = api.sendMessage(self.dataFB, contentSend, self.threadID)
               return _
     
     setCookies = "<cookies get from Facebook>"
     threadID = "<threadID>"
     client = fbchatClient(setCookies, threadID)
     dataFB = client.getData()
     listMessages = ['fbchat-v2 _⁠(⁠ツ⁠)⁠_']
     if (dataFB != 0):
          print("\033[1;92mLOGIN\033[0m Success")
          print("\033[1;92mDATABASE\033[0m Get messages....")
          
          try:
               while 1:
                    resultMessage = client.messageListen() # Nhận tin nhắn
                    if (client.dataFB["FacebookID"] != resultMessage["senderID"]): # Không nhận tin nhắn của bot
                         if listMessages[len(listMessages) - 1] != resultMessage['messageID']: # Kiểm tra tin nhắn cũ trong List
                              client.dataFB["messageID"] = resultMessage['messageID'] # Cập nhật messageID lên dataFB
                              print(f'\033[0mUser: \033[1;96m{resultMessage["senderID"]}\033[0m | Content: \033[1;96m{resultMessage["messageContents"]}\033[0m | IDMsg: \033[1;96m{resultMessage["messageID"]}\033[0m')
                              listMessages.append(resultMessage['messageID'])
                              match (resultMessage["messageContents"]):
                                   case "uptime": # Xem thời gian thực
                                        client.sendMsg(str(datetime.datetime.today()))
                                   case "ping": # Reply tin nhắn nếu thấy tin nhắn là 'ping'
                                        client.sendMsg('Pong!')
                                   case __: # Nhái lại tin nhắn người dùng
                                        client.sendMsg(str(resultMessage["messageContents"]))
          except: pass         
               
     else:
          raise SystemExit("\033[1;91mLOGIN\033[0m Failed.")
          
     # Author: MinhHuyDev
     # Datetime: 20:29 Thứ 6, 18/08/2023 (GMT + 7)

Sau đó, quay lại Terminal/CMD và chạy file này bằng cách:

.. code-block:: bash

 python mainBot.py

Nếu xảy ra lỗi và không chạy được, hãy thử lại bằng hay lệnh sau:

.. code-block:: bash

 python3 mainBot.py

hoặc

.. code-block:: bash

 py mainBot.py

💔Nếu vẫn xảy ra lỗi. Vui lòng kiểm tra xem đã tải Python về thiết bị hay chưa. Nếu chưa tải, hãy nhấp `vào đây <https://www.python.org/downloads/>`_ để được chuyển đến trang tải Python chính thức.

**🏅Dưới đây là ví dụ khi chạy được bot thành công**:

.. image:: https://i.ibb.co/fvJq87Z/Screenshot-2023-08-18-20-25-51-435-com-offsec-nethunter-kex.png

🫶🏻Cảm ơn bạn đã đọc đến đây! Nếu bạn vẫn còn **nhiều câu hỏi thắc mắc**. Hãy lướt xuống dưới để tìm **câu trả lời** cho riêng mình nhé :3 Yêuuuuuu

=======================================
Các câu hỏi thường gặp
=======================================

**1**. *Làm thế nào để lấy threadID?*

Rất đơn giản, đầu tiên bạn truy vào **www.facebook.com** và mở cuộc trò chuyện Messenger lên. Sau đó nhấp vào nút **Xem tất cả trong Messenger**, hình ảnh minh hoạ:

.. image:: https://i.ibb.co/X4ZqJm6/Screenshot-2023-08-18-20-49-08-436-com-offsec-nethunter-kex.png

**Bước tiếp theo**, bạn click vào *nhóm chat* cần lấy **ThreadID**. Lúc này trên thanh url của **website** sẽ hiện ra 1 dãy số, Việc cuối cùng bạn cần làm là **copy** dãy số đó. Hình ảnh minh hoạ:

.. image:: https://i.ibb.co/C1HvCyD/Screenshot-2023-08-18-19-54-43-383-com-offsec-nethunter-kex.png

=======================================
Thông báo về phiên bản mới
=======================================

*📢*: I am trying my best to complete receiving messages from **Facebook's websocket** as quickly as possible, however, I am encountering some issues with it, specifically: 

.. image:: https://i.ibb.co/L5kTYPX/Screenshot-2023-08-12-16-01-24-843-com-termux.png

I will try to fix it as soon as possible. Last update notification: 16:06 12/08/2023 (GMT +7)

=======================================
Thông tin liên hệ
=======================================

- **Facebook:** `Nguyễn Minh Huy :( !! <https://www.facebook.com/Booking.MinhHuyDev>`_
- **Telegram:** `MinhHuyDev <https://t.me/MinhHuyDev>`_
- **Website**: `mhuyz.dev <https://mhuyz.dev>`_
