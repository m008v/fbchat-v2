import requests
from _core._utils import parse_cookie_string, dataSplit

def dataGetHome(setCookies):
     
     mainRequests = {
          "headers": {
               "authority": "www.facebook.com",
               "method": "GET",
               "path": "/",
               "scheme": "https",
               "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
               "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
               "cache-control": "max-age=0",
               "cookie": setCookies,
               "dpr": "1.25",
               "priority": "u=0, i",
               "sec-ch-prefers-color-scheme": "dark",
               "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
               "sec-ch-ua-full-version-list": '"Chromium";v="140.0.7339.128", "Not=A?Brand";v="24.0.0.0", "Google Chrome";v="140.0.7339.128"',
               "sec-ch-ua-mobile": "?0",
               "sec-ch-ua-model": '""',
               "sec-ch-ua-platform": '"Windows"',
               "sec-ch-ua-platform-version": '"19.0.0"',
               "sec-fetch-dest": "document",
               "sec-fetch-mode": "navigate",
               "sec-fetch-site": "same-origin",
               "sec-fetch-user": "?1",
               "upgrade-insecure-requests": "1",
               "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
               "viewport-width": "493"
          },
          "timeout": 60000,
          "url": "https://www.facebook.com/",
          "cookies": parse_cookie_string(setCookies),
          "verify": True
     }
     
     dictValueSaved = {}
     splitDataList = [
          # FORMAT: nameValue, stringData_1, stringData_2
          ["fb_dtsg", "DTSGInitialData\",[],{\"token\":\"", "\""],
          ["fb_dtsg_ag", "async_get_token\":\"", "\""],
          ["jazoest", "jazoest=", "\""],
          ["hash", "hash\":\"", "\""],
          ["sessionID", "sessionId\":\"", "\""],
          ["FacebookID", "\"actorID\":\"", "\""],
          ["clientRevision", "client_revision\":", ","]
     ]
     
     sendRequests = requests.get(**mainRequests).text
     for i in splitDataList:
          nameValue = i[0]
          try:
               exportValue = dataSplit(i[1], i[2], HTML=sendRequests, defaultValue=True)
          except (IndexError, AttributeError, TypeError):
               exportValue = "Unable to retrieve data for %s. It's possible that they have been deleted or modified." % nameValue
          dictValueSaved[nameValue] = exportValue
     dictValueSaved["cookieFacebook"] = setCookies
     
     return dictValueSaved