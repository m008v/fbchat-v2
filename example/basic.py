
import json, random, datetime
from LorenBot.__module import (__messageData, 
                               __onMessenger,
                               __fbTools)

"""
 Code by MinhHuyDev
 Contact: https://www.facebook.com/minhuydev
 Github: https://github.com/minhuydev
 Datetime: 05:11 12/08/2022 (GMT + 7)
"""

def headersFacebook(setCookies):
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

def getMessengerText(threadID, cookieFB):
   getMessenger = __onMessenger.onMessenger.getListMessenger(threadID, cookieFB)
   messageToText = getMessenger["results"]["contents_text"]
#    messageID = getMessenger["results"]["messageID"]
#    authorID = getMessenger["results"]["senderID"]
#    timeStamp = getMessenger["results"]["timeStamp"]
   return messageToText
 def getDataFromFB(cookieFB):
    threadData = __fbTools.dataTools.dataGetHome(cookiesFB)
    return threadData
def commandReply(setCookies, threadID):
    
    """setCookies ->cookieFB"""

    Dataform = getDataFromFB(setCookies)

    while True:
        getMessengerText = getMessengerText(threadID, setCookies)
        if "hello" in getMessengerText:
            sendMessages = __messageData.api.sendMessage(threadData=Dataform
                                          threadContents="Hello, What help do you need? (LorenBot)",
                                          threadHeaders=headersFacebook(setCookies),
                                          threadID=threadID)
            print("COMMAND_REPLY: hello")
        elif "What time is it?" in getMessengerText:
            sendMessages = __messageData.api.sendMessage(threadData=Dataform
                                          threadContents="Datetime: " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                          threadHeaders=headersFacebook(setCookies),
                                          threadID=threadID)
            print("COMMAND_REPLY: datetime")
        else: pass


while True:
    try:
        commandReply("please enter your threadID", "please enter your cookieFB")
    except Exception as e:
        print("da xay ra loi:", str(e))
