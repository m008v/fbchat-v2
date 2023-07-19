import requests, threading, random
from utils import parse_cookie_string
"""
Được phát triển bởi Nguyễn Minh Huy, do vấn đề MessageListen khi đến một thời gian nhất định sẽ bị chặn tính năng (từ 1h đến 3 ngày). Nên từ đó MODULE này sẽ giải quyết được vấn đề đó :)
Được viết vào lúc 10:18 11/7/2023
"""

def antiBlockMain(setCookies, Url = "https://m.facebook.com"):
     listUrl = [
          "/home.php", # Trang chủ / Facebook.
          
          "/profile.php", # Trang cá nhân / Facebook
          
          "/friends/center/requests/", # Yêu cầu kết bạn / Facebook
          
          "/marketplace/hochiminhcity/", # Chợ / Facebook
          
          "/watch", # Watch / Facebook
          
          "/notifications.php", # Thông báo / Facebook
          
          "/buddylist.php", # Danh sách bạn bè đang hoạt động / Facebook
          
          "/bookmarks/", # Menu khác / Facebook
          
          "/onthisday/", # Ngày này năm xưa / Facebook
          
          "/saved/", # Đã lưu / Facebook
          
          "/events/", # Sự kiện / Facebook
          
          "/nt/?id=gaming", # Gaming / Facebook
          
          "/climatescienceinfo/", # Trung tâm khoa học khí hậu / Facebook
          
          "/help/", # Trung tâm trợ giúp / Facebook
          
          "/bugnub/", # Báo cáo sự cố / Facebook
          
          "/policies/", # Chính sách / Facebook
          
          "/language/", # Ngôn ngữ / Facebook
          
          "/privacy/center/", # Quyền riêng tư / Facebook
          
          "/groups/", # Nhóm / Facebook
          
          "/archive/", # Kho lưu trữ / Facebook
          
          "/hacked/" # Bảo vệ tài khoản / Facebook
          
     ]
     
     mainRequests = {
          "headers": {
              "Host": "m.facebook.com",
              "Connection": "keep-alive",
              "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
              "Sec-Fetch-Site": "none",
              "Sec-Fetch-Mode": "navigate",
              "Sec-Fetch-User": "?1",
              "Sec-Fetch-Dest": "document",
              "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
          },
          "timeout": 60000,
          "url": "{}{}".format(Url, random.choice(listUrl)), 
          "cookies": parse_cookie_string(setCookies),
          "verify": True
     }
     
     sendRequests = requests.get(**mainRequests)
     
     if (sendRequests.status_code == 200): 
          return 1
     else:
          return 0
          

"""
- vi: Bằng cách gửi hàng loạt requests nằm ở mọi tính năng ở Facebook Browser, chúng ta có thể lừa được hệ thống Facebook rằng đây là người dùng làm
- en: By sending batch requests across all features on Facebook Browser, we can deceive the Facebook system into thinking that it is a genuine user.
¯⁠\⁠_⁠(⁠ツ⁠)⁠_⁠/⁠¯
- vi: Điều kiện để dùng: Chạy 2 chương trình: Lấy tin nhắn từ nhóm và chạy module này bằng Threading Python
- en: Conditions to use: Run two programs: one to retrieve messages from a group and another to execute this module using Python Threading.
"""