FBChat-Remake: Open Source
=======================================

Xin chào, tôi là **MinhHuyDev**. Lời nói đầu, đây là lần đầu tiên mà mình làm lại một source lớn như vậy nên sẽ không tránh được những *sai sót* trong quá trình code, rất mong sẽ được người dùng báo cáo lại **Lỗi** tại issues của GitHub này nhé:3

.. image:: https://i.ibb.co/3TWntY6/Picsart-23-08-12-15-11-30-693.jpg

**👽Bạn không phải là người Việt Nam?**, bạn có thể đọc **README** (*ENGLISH*):  `tại đây <https://github.com/MinhHuyDev/fbchat-v2/blob/main/README_EN.rst>`_

**📢Dành cho người mới**: *Lướt xuống cuối trang bạn sẽ thấy* **TUTORIAL (Hướng dẫn)** *nhận tin nhắn và gửi tin nhắn nhé!*

=======================================
Thông tin cơ bản
=======================================

- **Được làm lại từ:** `𝘧𝘣𝘤𝘩𝘢𝘵 (𝘗𝘺𝘵𝘩𝘰𝘯) <https://fbchat.readthedocs.io/en/stable/>`_
- **Người đóng góp**: *hakuOwO*, *tranngocminh230791*
- **Ngôn ngữ lập trình:** `𝘗𝘺𝘵𝘩𝘰𝘯 <https://www.python.org/>`_
- **Phát triển bởi:** *Nguyễn Minh Huy*
- **Phiên bản hiện tại:** *1.0.4.3*
- **Cập nhật lần cuối:** *22:05 11/12/2023*
- **Vùng thời gian**: *GMT + 07*

=======================================
Có gì mới trong phiên bản này?
=======================================

**BIG UPDATE**: Tôi đã cập nhật việc nhận tin nhắn bằng *websocket* thay vì *requests* như trước. Bạn có thể xem chúng tại đây: `__messageListenV2.py <https://github.com/MinhHuyDev/fbchat-v2/blob/main/src/__messageListenV2.py>`_, Bây giờ bạn có thể nhận được tin nhắn với **tốc độ nhanh hơn**, và có thể **nhận tin nhắn nhiều nguồn khác nhau cùng lúc**. 

**BIG UPDATE 2**: Tôi đã cập nhật thêm tính năng cho `__sendMessage.py <https://github.com/MinhHuyDev/fbchat-v2/blob/main/src/__sendMessage.py>`_, bây giờ bạn có thể gửi tin nhắn cho cả nhóm và người dùng

**Hàm tính năng:** 

``listeningEvent()``

``updateDataAndSend()``


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

     # Waiting for update.
     # with websocket 😎

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

**🏅Dưới đây là ví dụ khi chạy được bot thành công**:

.. image:: https://i.ibb.co/fvJq87Z/Screenshot-2023-08-18-20-25-51-435-com-offsec-nethunter-kex.png

🫶🏻Cảm ơn bạn đã đọc đến đây! Nếu bạn vẫn còn **nhiều câu hỏi thắc mắc**. Hãy lướt xuống dưới để tìm **câu trả lời** cho riêng mình nhé :3 Yêuuuuuu

=======================================
Các câu hỏi thường gặp
=======================================

**1**. *Làm thế nào để lấy threadID?*

Rất đơn giản, đầu tiên bạn truy vào **www.facebook.com** và mở cuộc trò chuyện Messenger lên. Sau đó nhấp vào nút **Xem tất cả trong Messenger**, hình ảnh minh hoạ:

.. image:: https://i.ibb.co/GMx4Vsv/Screenshot-2023-08-20-13-36-43-263-com-offsec-nethunter-kex.png

**Bước tiếp theo**, bạn click vào *nhóm chat* cần lấy **ThreadID**. Lúc này trên thanh url của **website** sẽ hiện ra 1 dãy số, Việc cuối cùng bạn cần làm là **copy** dãy số đó. Hình ảnh minh hoạ:

.. image:: https://i.ibb.co/C1HvCyD/Screenshot-2023-08-18-19-54-43-383-com-offsec-nethunter-kex.png

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
