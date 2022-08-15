try:
 from re import search as regex
 from time import sleep
 from datetime import datetime
 #from requests_html import HTMLSession
 import json,os
 import requests
 from requests.sessions import Session
 from concurrent.futures import ThreadPoolExecutor
 from threading import Thread,local
 import __fbTools
except ImportError:
 pass
try:
  thread_local = local()
  def getSessionRequests() -> Session:
      if not hasattr(thread_local,'session'):
          thread_local.session = requests.Session()
      return thread_local.session

  def POST(url:str, headers, data):
      session = getSessionRequests()
      with session.post(url, headers=headers, data=data) as response:
          return {
            "contentsWebsite": response.text,
            "statusCode": response.status_code,
            "urlLocate": response.url,
            "timeRequests": response.elapsed.total_seconds()
          }
  def replyRequests(url, headers, data) -> None:
      with ThreadPoolExecutor(max_workers=10) as executor:
          var = POST(url, headers=headers, data=data)
          return var
  class api():
    def sendMessage(threadData:str,
                    threadContents:str,
                    threadHeaders:str,
                    threadID:str):
    
    # ajax = requests.Session()
    
      postForm = {}
      postForm["fb_dtsg"] = threadData["fb_dtsg"];
      postForm["jazoest"] = threadData["jazoest"];
      postForm["body"] = threadContents;
      postForm["send"] = "Gửi";
      postForm["tids"] = "cid.g."+threadID;
      postForm["csid"] = "LorenBot - with love (author Project: https://github.com/MinhHuyDev)";
    
      sendingPost = replyRequests("https://m.facebook.com/messages/send/?", headers=threadHeaders, data=postForm)
      
      try:
        if (str(sendingPost["urlLocate"]).split("request_type=")[1].split("&")[0].lower() == "send_success" and (sendingPost["statusCode"] == 200)):
          return True;
        else:
          return False;
      except Exception as errLog:
        raise SystemExit("\033[1;93mapi.sendMessage cho biết: " + str(errLog))

    
    def sendAdmin(threadData:str,
                  threadContents:str,
                  threadAdminID:str,
                  threadID:str,
                  threadHeaders:str,
                  setCookies:str):
    
      idUser = setCookies.split("user=")[1].split(";")[0];
      
      try:
        for adminID in threadAdminID:
          postForm = {}
          postForm["tids"] = "cid.c."+str(adminID)+":"+idUser;
          postForm["ids["+str(adminID)+"]"] = str(adminID);
          postForm["body"] = threadContents;
          postForm["fb_dtsg"] = threadData["fb_dtsg"];
          postForm["jazoes"] = threadData["jazoest"];
          postForm["__user"] = idUser;
  
          sendingPost = replyRequests("https://m.facebook.com/messages/send/?", headers=threadHeaders, data=postForm)
          # return sendingPost;
          try:
            if (str(sendingPost["urlLocate"]).split("request_type=")[1].split("&")[0].lower() == "send_success" and (sendingPost["statusCode"] == 200)):
              return True;
            else:
              return False;
          except:
            raise SystemExit("\033[1;93mapi.sendAdmin cho biết: " + str(errLog))
      finally: pass
      # except Exception as errLog:
      #   sendError = api.sendMessage(threadData, "Không thể gửi tin nhắn đến admin do đã xảy ra lỗi: " + str(errLog), threadHeaders, threadID)
    def sendUser(threadData:str,
                  threadContents:str,
                  threadHeaders:str,
                  UserID:str,
                  setCookies:str):
    

      idUser = setCookies.split("user=")[1].split(";")[0];

      postForm = {}
      postForm["tids"] = "cid.c."+str(UserID)+":"+str(idUser);
      postForm["ids["+str(UserID)+"]"] = str(UserID);
      postForm["body"] = threadContents;
      postForm["fb_dtsg"] = threadData["fb_dtsg"];
      postForm["jazoes"] = threadData["jazoest"];
      postForm["__user"] = idUser;

      sendingPost = replyRequests("https://m.facebook.com/messages/send/?", headers=threadHeaders, data=postForm)
      try:
        if (str(sendingPost["urlLocate"]).split("request_type=")[1].split("&")[0].lower() == "send_success" and (sendingPost["statusCode"] == 200)):
          return True;
        else:
          return False;
      except:
        raise SystemExit("\033[1;93mapi.sendUser cho biết: " + str(errLog))
except Exception as errLog:
  print("\033[1;93mERROR: \033[1;97m" + str(errLog))

# setCookies = ''
# data = __fbTools.dataTools.dataGetHome(setCookies)
# headers = __fbTools.Headers(setCookies)
# listad = [4]
# for i in range(1):
#   var = api.sendUser(data, "djt me m mark", headers, "4", setCookies)
#   print(var)
