FacebookChat for Python: README.rst
=======================================

.. image:: https://i.ibb.co/bmB7MQT/image.png


Xin chào, tôi là MinhHuyDev. Đây là gói module hỗ trợ cho **`LorenBot`**, không chỉ dùng được cho
bot, mà nó còn có thể áp dụng cho nhiều loại tool khác nhau :D Cùng đọc README để biết thêm chi tiết nhé!

Những ưu điểm tiêu biểu của gói module này:

- **Hỗ trợ mọi loại thiết bị (Yêu cầu Python > 3.9)**
- **Dễ dàng sử dụng**
- **Dễ dàng chỉnh sửa code**
- **Tốc độ xử lý nhanh (0.1~1.5s)**

.. Other nice features include:

    - Markdown export of pages and elements.


*EXAMPLE*: **Hướng dẫn lấy dữ liệu cần thiết từ Facebook**
================

***HƯỚNG DẪN IMPORT MODULE TỪ FOLDER***


Example: 


- Folder Name: **`LorenBotModule`**
- FileModule Name: **`__fbTools**, **__messageData`**

.. code-block:: python

    >>> from LorenBotModule.__fbTools import *
    >>> from LorenBotModule.__messageData import *
    >>> cookiesFB = "please enter your FB cookie"
    >>> threadData = __fbTools.dataTools.dataGetHome(cookiesFB)
    >>> print(threadData)
    
 
**Kết quả (khi lấy dữ liệu thành công):**

.. code-block:: json

    {
        "status": 200,
        "fb_dtsg": "NAcNHJpSM......", 
        "fb_dtsg_ag": "AQzivFLhZS_Dm4V-Pgdf.........", 
        "sessionID": "16580732-26.......", 
        "clientID": "ed5296b1-b7da-4.....", 
        "appID": "222039.....", 
        "jazoest": "25...", 
        "lsd": "aO00EheU........",
        "hash": "AT5s0V0E-......."
    }


Hoặc nó sẽ ra **LỖI** khi không GET được data:

.. code-block:: json

    {
        "status": -1,
        "fb_dtsg": null,
        "fb_dtsg_ag": null,
        "sessionID": null,
         "clientID": null,
         "appID": null,
         "jazoest": null,
         "lsd": null,
         "hash": null
    }
    

*Chi tiết:* lỗi này xảy ra khi không lấy được dữ liệu từ máy chủ **FACEBOOK**. Không sao cả bạn có thử chạy lại
file code để lấy lại dữ liệu.


Bạn nghĩ đó là những gì toàn tệ nhất? **KHÔNG** đây mới là điều tồi tệ nhất:

.. code-block:: json

    {
        "error": true,
         "error_code": 404,
         "status": 404,
         "error_description": "Mô tả chi tiết lỗi......."
     }
    
 
*Chi tiết:* Lỗi này xảy ra khi không thể kết nối đến máy chủ **FACEBOOK** hoặc đã xảy ra lỗi khi thực thi code
(xem thêm tại key 'error_description')

*EXAMPLE*: **Nhận tin nhắn và trả lời tin nhắn threadID**
================
**Cách Lấy ThreadID:**




 
================
.. code-block:: python


        import json, random, datetime
        from LorenBotModule import (__messageData, 
                                    __onMessenger,
                                    __fbTools)

        """
         Code by MinhHuyDev
         Contact: https://www.facebook.com/minhhuydev
         Github: https://github.com/minhhuydev
         Datetime: 05:11 12/08/2022 (GMT + 7)
        """

        # Please check below url to see more.... (URl: /fbchat-v2/example/basic.py)
        

**XEM THÊM TẠI:** *https://bit.ly/3drv3UO*

**KẾT QUẢ KHI CHẠY THÀNH CÔNG**

- **Kết quả tại đây (Response):** *None Url*

*Dự Án ChatBot Messenger Python (LorenBot)*
================
 .. image:: https://i.ibb.co/bQ0PKYh/Screenshot-2023-06-11-10-08-40-546-mark-via-gp.png
================
Lịch sử cập nhật fbchat-v2
================
  - **Ngày tạo Repositories:** 2022-07-21 00:34:33
  - **Cập nhật đợt 1:** 2022-07-21 
  - **Cập nhật đợt 2 (BIG UPDATE):** 2022-8-12
  - **Cập nhật đợt 3 (BIG UPDATE):** YYYY-MM-DD

Liên hệ,hỗ trợ & MXH khác
================

**Hãy nhớ dùng não và ý thức của bản thân để có một cuộc trò chuyện
mà mình có thể hỗ trợ tốt nhất nhé!**


- **Facebook:** *https://www.facebook.com/Booking.MinhHuyDev*
- **Instagram:** *https://www.instagram.com/MinhHuyDev*
- **Youtube:** *https://www.youtube.com/MinhHuyDev*
- **Github:** *https://www.github.com/MinhHuyDev*
- **Tiktok:** *https://www.tiktok.com/@MinhHuyDev*
- **Telegram:** *https://www.telegram.org/MinhHuyDev*
- **Zalo:** *https://www.zalo.me/MinhHuyDev*
- **Website:** *https://www.mhuyz.dev*
- **Room Discord:** *https://discord.gg/bCdq4RyAvb*

