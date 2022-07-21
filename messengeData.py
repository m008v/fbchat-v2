try:
 from re import search as regex
 from time import sleep
 from datetime import datetime
 #from requests_html import HTMLSession
 import json,os
 import requests
except ImportError:
 pass
try:
 class api():
  def sendMessage(threadData,
                      threadContents,
                      threadHeaders,
                      threadID,
                      setCookies):
  
   ajax = requests.Session()
  
   postForm = {}
   postForm["fb_dtsg"] = threadData["fb_dtsg"];
   postForm["jazoest"] = threadData["jazoest"];
   postForm["body"] = threadContents;
   postForm["send"] = "Gửi";
   postForm["tids"] = "cid.g."+threadID;
   postForm["csid"] = "LorenBot - with love";
   
   threadSeding = ajax.post(
   "https://m.facebook.com/messages/send/?",
   headers=threadHeaders,
   data=postForm
   ).text;
   
  def sendNotification(threadData,
                        threadContents,
                        threadHeaders,
                        threadID,
                        setCookies):
 
   ajax = requests.Session()
   
   postForm = {}
   postForm["fb_dtsg"] = regex('rename="fb_dtsg" value=".*"', threadData)[0].replace('rename="fb_dtsg" value="', '').replace('"','')
   postForm["jazoest"] = threadData.split('name="jazoest" value="')[1].split('" autocomplete="off" />')[0];
   postForm["body"] = threadContents;
   postForm["send"] = "Gửi";
   postForm["tids"] = "cid.g."+threadTIDBox;
   postForm["csid"] = threadData.split('name="csid" value="')[1].split('" /></form>')[0];
   
   threadSeding = ajax.post(
   "https://m.facebook.com/messages/send/?",
   headers=threadHeaders,
   data=postForm
   ).text;
   
   
  def sendAdmin(threadData,
               threadContents,
               threadHeaders,
               setCookies):
  
   ajax = requests.Session();
   idUser = setCookies.split("user=")[1].split(";")[0];

   for adminID in json.loads(open(os.path.dirname("/storage/emulated/0/Download/LorenBot/") + "/configMain.json","r").read())["LORENBOT"]["adminList"]:
    postForm = {}
    postForm["tids"] = "cid.c."+adminID+":"+idUser;
    postForm["ids["+adminID+"]"] = adminID;
    postForm["body"] = threadContents;
    postForm["fb_dtsg"] = threadData["fb_dtsg"];
    postForm["jazoes"] = threadData["jazoest"];
    postForm["__user"] = idUser;

    threadSeding = ajax.post(
    'https://m.facebook.com/messages/send/?',
    headers=threadHeaders,
    data=postForm
    )
    
  def sendUser(threadData,
                 threadContents,
                 threadHeaders,
                 UserID,
                 setCookies):
   
   ajax = requests.Session()
   idUser = setCookies.split("user=")[1].split(";")[0];
   postForm = {}
   postForm["tids"] = "cid.c."+UserID+":"+idUser;
   postForm["ids["+UserID+"]"] = UserID;
   postForm["body"] = threadContents;
   postForm["fb_dtsg"] = threadData["fb_dtsg"];
   postForm["jazoes"] = threadData["jazoest"];
   postForm["__user"] = idUser;

   threadSeding = ajax.post(
   'https://m.facebook.com/messages/send/?',
   headers=threadHeaders,
   data=postForm
   )

except Exception as errLog:
  print("Đã xảy ra lỗi: "+ str( errLog ))


# print(api.sendAdmin('zinh bịp',"","",""))
