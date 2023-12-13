import random, attr, requests, json
import __facebookToolsV2
from utils import str_base, digitToChar, mimetype_to_key, require_list, get_files_from_paths

def _uploadAttachment(filenames, dataFB):

     
     USER_AGENTS = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 (KHTML, like Gecko) Version/8.0.5 Safari/601.1.10", "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1", "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6"]
     
     headers = {
          "Referer": "https://www.facebook.com",
          "Accept": "text/html",
          "User-Agent": random.choice(USER_AGENTS),
          "Cookie": dataFB["cookieFacebook"],
     }
     
     files = get_files_from_paths(filenames)
     __reg = attr.ib(0).counter
     __reg += 1
     dataForm = {} 
     dataForm["voice_clip"] = False
     dataForm["__a"] = 1
     dataForm["__req"] = str_base(__reg, 36) 
     dataForm["fb_dtsg"] = dataFB["fb_dtsg"]

     file_dict = {
          "upload_{}".format(i): f for i, f in enumerate(files)
     }
     
     resultRequests = requests.post("https://upload.facebook.com/ajax/mercury/upload.php", headers=headers, data=dataForm, files=file_dict).text
     
     try: 
          resultRequests = json.loads(resultRequests.replace("for (;;);", ""))["payload"]
     except: 
          return print("ERROR-UPLOADED: " + str(resultRequests))
     
     resultData = [
                 (data[mimetype_to_key(data["filetype"])], data["filetype"])
                 for data in resultRequests["metadata"]
     ]
     
     return {
          "attachmentID": resultData[0][0],
          "attachmentUrl": resultRequests["metadata"][0]["src"],
          "attachmentType": resultData[0][1],
          "attachmentDataSend": resultData
     }


# _uploadAttachment("<name file to need upload>", dataFB)
# print(_uploadAttachment("FB_IMG_1662921262503.jpg", __facebookToolsV2.dataGetHome("this is Cookie Facebook")))
# output: {'attachmentID': 676421537934928, 'attachmentUrl': 'https://scontent.fsgn5-8.fna.fbcdn.net/v/t1.15752-9/328999258_555852780015611_2452318447980968642_n.jpg?_nc_cat=109&ccb=1-7&_nc_sid=b65b05&_nc_ohc=ngkZ0e3NqzYAX8ZdVYx&_nc_ht=scontent.fsgn5-8.fna&oh=03_AdTrTWSDqWiSrYcTG8c_WKn1ksUdttUbcK3hmvTu2WEmRQ&oe=65A10D97', 'attachmentType': 'image/jpeg', 'attachmentDataSend': [(676421537934928, 'image/jpeg')]}

# completed at 14:03 19/06/2023 | last updated at 19:23 13/12/2023
