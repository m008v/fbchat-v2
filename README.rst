FacebookChat for Python
=======================================

Xin chào, tôi là MinhHuyDev. Đây là gói module hỗ trợ cho **`LorenBot`**, không chỉ dùng được cho bot, mà nó còn có thể áp dụng cho nhiều loại tool khác nhau :D Cùng đọc README để biết thêm chi tiết nhé!

.. image:: https://camo.githubusercontent.com/467b153c8738634f7c04b5e86941ab807f329ff432acaf3ea01a0ea78892a985/68747470733a2f2f692e6962622e636f2f7644356d5632322f506963736172742d32332d30362d31372d31372d30382d33342d3036372e6a7067

**Thông tin cơ bản về FBChat V2:**

- **Được lấy ý tưởng từ:** *fbchat*
- **Người đóng góp**: *KanzuWakazaki* **,** *hakuOwO*
- **Ngôn ngữ lập trình:** *Python*
- **Phát triển bởi:** *Nguyễn Minh Huy*
- **Phiên bản hiện tại:** *2.0.1*
- **Cập nhật lần cuối:** *17:38 17/06/2023*

================

**DEMO** *Login Facebook with Username & Password:* 

.. image:: https://i.ibb.co/bmB7MQT/image.png

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
    >>> cookiesFB = "datr=....; sb=.....; m_pixel_ratio=......; fr=......; ....."
    >>> threadData = __fbTools.dataTools.dataGetHome(cookiesFB)
    >>> threadData
    
 
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


Hoặc nó sẽ ra **LỖI** khi không GET được dữ liệu:

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
    

*Chi tiết:* lỗi này xảy ra khi không lấy được dữ liệu từ máy chủ **FACEBOOK** (**Die Cookie, Requests timeout**). Không sao cả bạn có thử chạy lại chương trình để thử lại.


**Lỗi code**: Đây là *JSON* khi có lỗi code xảy ra (có thể xảy ra khi dữ liệu được **Facebook** thay đổi):

.. code-block:: json

    {
        "error": true,
         "error_code": 404,
         "status": 404,
         "error_description": "Mô tả chi tiết lỗi......."
     }
    
 
*Chi tiết:* 

*EXAMPLE*: **Nhận tin nhắn và trả lời tin nhắn threadID**
================
*Cách Lấy* **ThreadID** *Trên Messenger:*

.. image:: https://i.ibb.co/n1k4cPk/IMG-20230611-101906.jpg

Tại đường dẫn vào nhóm (thread). Trên *URL của Messenger* sẽ hiện thị một dãy số nằm sau **messenger.com/t/** hãy copy dãy số đó và dán tại 1 biến (variable) cho **ThreadID** để có thể gửi tin nhắn đến nhóm đã được chọn/chỉ định.

================

.. code-block:: python


        import json, random, datetime
        from LorenBotModule import (__messageData, 
                                    __onMessenger,
                                    __fbTools)

        """
         Code by MinhHuyDev
         Contact: https://www.facebook.com/booking.minhhuydev
         Github: https://github.com/minhhuydev
         Datetime: 05:11 12/08/2022 (GMT + 7)
        """

        # Please check below url to see more.... (URl: /fbchat-v2/example/basic.py)
        

**XEM THÊM TẠI:** *https://bit.ly/3drv3UO*

**KẾT QUẢ KHI CHẠY THÀNH CÔNG**

- **Kết quả tại đây (Response):** *None Url*


*Dự Án ChatBot Messenger Python (LorenBot)*
================
**Ngày thực hiện dự án**: *07/11/2021* | **Đã hoàn thành**: *81.5%* | **Tác giả**: *Nguyễn Minh Huy*

.. image:: https://i.ibb.co/pryHzBD/Screenshot-2023-06-17-11-46-43-542-mark-via-gp.png

================
Lịch sử cập nhật fbchat-v2
================
- **Ngày tạo Repositories:** 21-07-2022 *00:34:33*
- **Cập nhật đợt 1:** 21-07-2022
- **Cập nhật đợt 2 (BIG UPDATE):** 12-08-2022
- **Cập nhật đợt 3 (BIG UPDATE):** 11-06-2023

Liên hệ,hỗ trợ & MXH khác
================

**Hãy nhớ dùng não và ý thức của bản thân để có một cuộc trò chuyện
mà mình có thể hỗ trợ tốt nhất nhé!**


- **Facebook:** *https://www.facebook.com/Booking.MinhHuyDev*
- **Youtube:** *https://www.youtube.com/MinhHuyDev*
- **Github:** *https://www.github.com/MinhHuyDev*
- **Telegram:** *https://www.telegram.org/MinhHuyDev*
- **Zalo:** *https://www.zalo.me/MinhHuyDev*
- **Website:** *https://www.mhuyz.dev*
- **Room Discord:** *https://discord.gg/bCdq4RyAvb*

