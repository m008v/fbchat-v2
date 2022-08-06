FacebookChat for Python: README.rst
=======================================

.. image:: https://i.ibb.co/gDkp3GP/facebook-chat-messenger-for-python-611ae2e22a45e-375x210.png

.. image:: https://travis-ci.com/psf/requests-html.svg?branch=master
    :target: https://travis-ci.com/psf/requests-html

Xin chào, tôi là MinhHuyDev. Đây là gói module hỗ trợ cho `LorenBot`, không chỉ dùng được cho
bot, mà nó còn có thể áp dụng cho nhiều loại tool khác nhau :D Cùng xem README để biết thêm chi tiết nhé!

Những ưu điểm tiêu biểu của gói module này:

- **Hỗ trợ mọi loại thiết bị (miễn là chạy được Python:)))**
- **Dễ dàng sử dụng**
- **Dễ dàng chỉnh sửa code**
- **Sử dụng requests_html nên tỉ lệ bị die acc là không cao**

.. Other nice features include:

    - Markdown export of pages and elements.


Hướng dẫn & Cách sử dụng
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
    
 
**Kết quả:**

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
    

