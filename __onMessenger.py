import requests_html
import datetime
from requests.sessions import Session
from concurrent.futures import ThreadPoolExecutor
from threading import Thread,local
import requests
import random
import json

ConfigEvent = {
    "Credits": "Nguyen Minh Huy",
    "Tester": "Tran Trong Hoa",
    "Botname": "LorenBot / Zerbot",
    "Debug": "7/11/2021",
    "mdlDownload": [
        "https://api.minhhuy.dev/lorenbot-project/MODULE_BOT_PROJECT.php"
    ],
    "HTMLOptions": [
        {
            "getMessenger": [
                {
                    'begin': '<div class="_34ej">',
                    'end': '</div></div></div></span><div class='
                }
            ],
            "messageID": [
                {
                    'begin': ',&quot;uuid&quot;:&quot;',
                    'end': '&quot;'
                }
            ],
            "AuthorIDxTimeStamp": [
                {
                    'begin': 'data-store="&#123;&quot;timestamp&quot;:',
                    'begin-r': ',&quot;author&quot;:',
                    'end': ',&quot;uuid&quot;:&quot;'
                }
            ]
        }
    ]
};

thread_local = local()

def getSessionRequests() -> Session:
      if not hasattr(thread_local,'session'):
          thread_local.session = requests.Session()
      return thread_local.session

def GET(url:str, headers):
      session = getSessionRequests()
      with session.get(url, headers=headers) as response:
          return {
            "contentsWebsite": response.text,
            "statusCode": response.status_code,
            "urlLocate": response.url,
            "timeRequests": response.elapsed.total_seconds()
          }
def replyRequests(url, headers) -> None:
      with ThreadPoolExecutor(max_workers=10) as executor:
          var = GET(url, headers=headers)
          return var

session = requests_html.HTMLSession()
listContentsMessage = []
class onMessenger():
    def headersFacebook(setCookies):
        # openRandomUseragent = open("./__cache__/userAgentList.txt").read().splitlines()
        # userAgentRandom = str(random.choice(openRandomUseragent))
        headers = {}
        headers["Connection"] = "keep-alive";
        headers["Keep-Alive"] = "300";
        headers["authority"] = "m.facebook.com";
        headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36";
        headers["accept-Charset"] = "ISO-8859-1,utf-8;q=0.7,*;q=0.7";
        headers["accept-language"] = "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5";
        headers["cache-control"] = "max-age=0";
        headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9";
        headers["sec-fetch-site"] = "none";
        headers["sec-fetch-mode"] = "navigate";
        headers["sec-fetch-user"] = "?1";
        headers["sec-fetch-dest"] = "document";
        headers["cookie"] = setCookies;
        return headers;

    def messageReceived(typeCommand, typeContents):
        if typeCommand == 'added':
            listContentsMessage.append(str(typeContents))
        elif typeCommand == 'removed':
            pass
        elif typeCommand == 'count':
            countMessage = len(listContentsMessage)
            return countMessage
        else:
            return 0;
    def checkThread(threadID, setCookies):
        print("\033[0mStarting.......")
        threadId = str(threadID)
        print("\033[0mTHREAD ID: " + threadId)
        # url = "https://www.messenger.com/api/v1/me
        headersFB = onMessenger.headersFacebook(setCookies)
        # print(headersFB)
        checking = session.get("https://m.facebook.com/messages/read/?tid=" + threadId, headers=headersFB)
        checkTitle = checking.text.split("<title>")[1].split('</title>')[0]
        if (checkTitle == "New Message" or (checkTitle == "Tin nhắn mới")):
            return {
                "status": "error",
                "description": "This is an invalid message. Please try again."
            }
        elif (checkTitle == "Không tìm thấy nội dung"):
            return {
                "status": "error",
                "description": "setCookie error. Please try again."
            }
        else:
            return {
                "status": "ok",
                "description": ""
            }

    def getListMessenger(threadID, setCookies):
        threadId = str(threadID)
        addedNull = onMessenger.messageReceived(typeCommand="added",
        typeContents="khong co j dau")
        # checkThread = onMessenger.checkThread(threadId, setCookies)
        # if (checkThread["status"] == "error"):
        #     raise SystemExit("\033[1;91m" + checkThread["description"])
        while True:
            headersFB = onMessenger.headersFacebook(setCookies)
            __getMessenger = replyRequests("https://m.facebook.com/messages/read/?tid=" + threadId, headers=headersFB)
            if __getMessenger["statusCode"] == 200:
                # __getMessenger.encoding = "utf-8"
                __getMessenger_contents = __getMessenger["contentsWebsite"]
                try:
                    __getMessenger_message_length = __getMessenger_contents.count(ConfigEvent['HTMLOptions'][0]['getMessenger'][0]['begin'])
                    __getMessenger_senderID_length = __getMessenger_contents.count(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin'])
                    __getMessenger_messageID_length = __getMessenger_contents.count(ConfigEvent['HTMLOptions'][0]['messageID'][0]['begin'])
                    __getMessenger_timeStamp_length = __getMessenger_contents.count(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin'])
                    __getMessenger_content_new_message = __getMessenger_contents.split(ConfigEvent['HTMLOptions'][0]['getMessenger'][0]['begin'])[__getMessenger_message_length].split(ConfigEvent['HTMLOptions'][0]['getMessenger'][0]['end'])[0]
                    __getMessenger_senderID = __getMessenger_contents.split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin'])[__getMessenger_senderID_length].split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin-r'])[1].split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['end'])[0]
                    __getMessenger_messageID = __getMessenger_contents.split(ConfigEvent['HTMLOptions'][0]['messageID'][0]['begin'])[__getMessenger_messageID_length].split(ConfigEvent['HTMLOptions'][0]['messageID'][0]['end'])[0]
                    __getMessenger_timeStamp = __getMessenger_contents.split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin'])[__getMessenger_timeStamp_length].split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['begin-r'])[1].split(ConfigEvent['HTMLOptions'][0]['AuthorIDxTimeStamp'][0]['end'])[0]
                except Exception as errLog:
                    if str(errLog).lower() == "list index out of range":
                        return {
                            "status": "error"    
                        }
                if __getMessenger_senderID+"_"+__getMessenger_content_new_message+"_"+__getMessenger_timeStamp+"_"+__getMessenger_messageID in listContentsMessage[int(len(listContentsMessage)) - 1]:
                    pass 
                else:
                    listContentsMessage.append(__getMessenger_senderID+"_"+__getMessenger_content_new_message+"_"+__getMessenger_timeStamp+"_"+__getMessenger_messageID)
                    __getMessenger_encodeToJSon = {
                        "status": "OK",
                        "results": {
                            "contents_text": __getMessenger_content_new_message,
                            "senderID": __getMessenger_senderID,
                            "messageID": __getMessenger_messageID,
                            "timeStamp": __getMessenger_timeStamp
                        },
                        "length": [
                            __getMessenger_message_length,
                            __getMessenger_senderID_length,
                            __getMessenger_messageID_length,
                            __getMessenger_timeStamp_length
                        ],
                        "infomation": {
                            "accountID": setCookies.split("user=")[1].split(";")[0],
                            "threadID": threadID, 
                            "messageReceived": len(listContentsMessage),
                            "totalTimeRequests": __getMessenger["timeRequests"],
                            "dateTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    }
                # print(__getMessenger_encodeToJSon)

                return __getMessenger_encodeToJSon



while True:
    var = onMessenger.getListMessenger(threadID="",
                                    setCookies="")
    print(var)


