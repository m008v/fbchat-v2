"""
Author: MinhHuyDev - Github
Datetime: 21:23 thứ 7 ngày 17/06/2023
Remake from fbchat-python
"""
import random, attr
from os.path import basename
from mimetypes import guess_type 
import requests, json
# from LorenBot.plugins import __facebookToolsV2
import __facebookToolsV2
from utils import str_base, digitToChar
def Main(filenames, setCookies, dataGet):

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
     
     getData = dataGet
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
     
     resultRequests = requests.post("https://upload.facebook.com/ajax/mercury/upload.php", headers=headers, data=dataForm, files=file_dict).text
     
     try: resultRequests = json.loads(resultRequests.replace("for (;;);", ""))["payload"]
     except: return resultRequests
     
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

# print(Main("2.original.jpg", "datr=rM9tZIpb9TtHPOWv5NL-NqZl;sb=rM9tZLiOL3cWEFe-nC3mrNhY;vpd=v1%3B789x396x2.731250047683716;dpr=2.731250047683716;wl_cbv=v2%3Bclient_version%3A2272%3Btimestamp%3A1686825055;locale=vi_VN;wd=396x789;fr=0aNDB5Ay7UZSJ1zr0.AWXSXac5SXnOiDEbInsSjT2EEp0.Bkbt-d.k7.AAA.0.0.Bki0OI.AWWHXUol6jU;c_user=100090180575190;xs=26%3A6ropO2Rkk9ud4w%3A2%3A1686848393%3A-1%3A6276;fbl_cs=AhD8%2FNxB822GJRri9EFiVMlZGEF2L2FsN1l2UThyZ2d3VDNOc3JKTndQbA;fbl_ci=242920415009247;fbl_st=101435741%3BT%3A28116284;"))
""" Hướng dẫn sử dụng (Tutorial)

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
✓Hoàn thành vào lúc 14:03 ngày 19/6/2023 • Cập nhật mới nhất: 8:03 20/7/2023
✓Tôn trọng tác giả ❤️
"""
