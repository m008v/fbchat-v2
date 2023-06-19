"""
Author: MinhHuyDev - Github
Datetime: 21:23 thứ 7 ngày 17/06/2023
Remake from fbchat-python
"""
import random, attr
from os.path import basename
from mimetypes import guess_type
import requests, json
from LorenBot.plugins import __fbTools
def Main(filenames, setCookies):
     def digitToChar(digit):
          if digit < 10:
               return str(digit)
          return chr(ord("a") + digit - 10)
     
     
     def str_base(number, base):
          if number < 0:
               return "-" + str_base(-number, base)
          (d, m) = divmod(number, base)
          if d > 0:
               return str_base(d, base) + digitToChar(m)
          return digitToChar(m)
     def mimetype_to_key(mimetype):
          if not mimetype:
              return "file_id"
          if mimetype == "image/gif":
              return "gif_id"
          checkData = mimetype.split("/")
          if checkData[0] in ["video", "image", "audio"]:
               return "%s_id" % checkData[0]
          return "file_id"
     
     USER_AGENTS = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 (KHTML, like Gecko) Version/8.0.5 Safari/601.1.10", "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1", "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6"]
     
     getData = __fbTools.dataTools.dataGetHome(setCookies)
     headers = {
     "Referer": "https://www.facebook.com",
     "Accept": "text/html",
     "User-Agent": random.choice(USER_AGENTS),
     "Cookie": setCookies
     }
     def require_list(list_):
          if isinstance(list_, list):
               return set(list_)
          else:
               return set([list_])
     def get_files_from_paths(filenames):
          
          files = [filenames, open(filenames, "rb"), guess_type(filenames)[0]]
          yield files
     
     files = get_files_from_paths(filenames)
     __reg = attr.ib(0).counter
     __reg += 1
     dataForm = {} 
     dataForm["voice_clip"] = False
     dataForm["__a"] = 1
     dataForm["__req"] = str_base(__reg, 36) 
     dataForm["fb_dtsg"] = getData["fb_dtsg"]

     file_dict = {"upload_{}".format(i): f for i, f in enumerate(files)}
     
     resultRequests = json.loads(requests.post("https://upload.facebook.com/ajax/mercury/upload.php", headers=headers, data=dataForm, files=file_dict).text.replace("for (;;);", ""))["payload"]
     
     resultData = [
                 (data[mimetype_to_key(data["filetype"])], data["filetype"])
                 for data in resultRequests["metadata"]
     ]
     
     return {
          "idImage": resultData[0][0],
          "urlImage": resultRequests["metadata"][0]["src"],
          "typeImage": resultData[0][1],
          "dataSend": resultData
     }


""" Hướng dẫn sử dụng (User manual)

 * Dữ liệu yêu cầu (args):
 
     - getData: lấy từ __fbTools
     - filenames: đường dẫn đến ảnh (VD: "../DCIM/100PINT/Ghim/aecc74......png/jpg/...)
     - setCookies: cookie tài khoản FB

* Kết quả trả về:
     
     Không có thông tin

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 14:03 ngày 19/6/2023
✓Tôn trọng tác giả ❤️
"""