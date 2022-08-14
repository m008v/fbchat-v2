import re,json,time,random
from requests_html import HTMLSession
from bs4 import BeautifulSoup as BS
from requests import get as GET
session = HTMLSession()
def Headers(setCookies):
    Headers={};
    Headers["Connection"] = "keep-alive"
    Headers["Keep-Alive"] = "300"
    Headers["authority"] = "m.facebook.com"
    Headers["user-agent"] = "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
    Headers["ccept-Charset"] = "ISO-8859-1,utf-8;q=0.7,*;q=0.7"
    Headers["accept-language"] = "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5"
    Headers["cache-control"] = "max-age=0"
    Headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    Headers["sec-fetch-site"] = "none"
    Headers["sec-fetch-mode"] = "navigate"
    Headers["sec-fetch-user"] = "?1"
    Headers["sec-fetch-dest"] = "document"
    Headers["cookie"] = setCookies
    return Headers;
class dataTools():
    def dataGetHome(setCookies):
        try:
            raw = HTMLSession().get('https://www.facebook.com',headers=Headers(setCookies)).text
            fb_dtsg = raw.split('token":"')[2]
            fb_dtsg_ag = raw.split('"async_get_token":"')[1]
            session_id = re.findall('"sessionID":".*?"',raw)
            client_id = re.findall('"clientID":".*?"',raw)
            jazoest = raw.split('jazoest=')[1].split('"')[0]
            lsd = raw.split('LSD",[],{"token":"')[1].split('"')[0]
            hash = raw.split('"result":true,"hash":"')[1].split('"')[0]
            app_id = raw.split('[],{"appId":')[1].split(',')[0]
            if (len(fb_dtsg) > 0 and (len(fb_dtsg_ag) and (len(session_id) > 0 and (len(client_id) > 0 and (len(lsd) > 0 and (len(hash) > 0 and (len(app_id) > 0))))))):
                fb_dtsg=fb_dtsg.split('"')[0]
                fb_dtsg_ag=fb_dtsg_ag.split('"')[0]
                session_id = session_id[0].split('"sessionID":"')[1].split('"')[0]
                client_id = client_id[0].split('"clientID":"')[1].split('"')[0]
                return {
                    "status": 200,
                    "fb_dtsg": fb_dtsg,
                    "fb_dtsg_ag": fb_dtsg_ag,
                    "sessionID": session_id,
                    "clientID": client_id,
                    "appID": app_id,
                    "jazoest": jazoest,
                    "lsd": lsd,
                    "hash": hash
                }
            else:
                return {
                    "status": -1,
                    "fb_dtsg": None,
                    "fb_dtsg_ag": None,
                    "sessionID": None,
                    "clientID": None,
                    "appID": None,
                    "jazoest": None,
                    "lsd": None,
                    "hash": None
                }
        except Exception as errorLog:
            return {
                "error": True,
                "error_code": 404,
                "status": 404,
                "error_description": str(errorLog)
            }
