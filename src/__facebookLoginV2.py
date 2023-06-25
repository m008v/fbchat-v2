import requests
import re
import hashlib
import string
import random
import json
import html
from bs4 import BeautifulSoup as BS

"""
Written by Nguyen Minh Huy (RainTee)
Facebook Login V2 - Fixed
Updated: 28/12/2022
"""

def randStr(length):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def GetToken2FA(key2Fa):
    twoFARequests = json.loads(requests.get("https://2fa.live/tok/" + key2Fa.replace(" ","")).text)
    return twoFARequests["token"]


def Headers(cookiesFB=None):
     headers={}
     headers["Host"] = "mbasic.facebook.com";
     headers["origin"] = "https://mbasic.facebook.com";
     headers["content-type"] = "application/x-www-form-urlencoded";
     headers["user-agent"] = "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36";
     headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9";
     headers["referer"] = "https://mbasic.facebook.com/login/?";
     headers["accept-language"] = "en-US,en;q=0.9";
     headers["x-requested-with"] = "mark.via.gp";
     headers["cookie"] = cookiesFB;
     return headers
def loginFacebook(userFB=None, passFB=None, authenticationGG=None):
     SessionRQ = requests.Session()
     
     headers = {
          "Host": "b-graph.facebook.com",
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Fb-Connection-Type": "unknown",
          "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G988N Build/NRD90M) [FBAN/FB4A;FBAV/340.0.0.27.113;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/324485361;FBCR/Viettel Mobile;FBMF/samsung;FBBD/samsung;FBDV/SM-G988N;FBSV/7.1.2;FBCA/x86:armeabi-v7a;FBDM/{density=1.0,width=540,height=960};FB_FW/1;FBRV/0;]",
          "X-Fb-Connection-Quality": "EXCELLENT",
          "Authorization": "OAuth null",
          "X-Fb-Friendly-Name": "authenticate",
          "Accept-Encoding": "gzip, deflate", 
          "X-Fb-Server-Cluster": "True",
     }
     
     device_id = randStr(8) +"-"+randStr(4) +"-"+ randStr(4)+"-"+ randStr(4) +"-"+ randStr(12)
     adid = randStr(8)+"-" +randStr(4)+"-" + randStr(4)+"-"+ randStr(4)+"-" + randStr(12)
     secure_family_device_id =randStr(8)+"-" +randStr(4)+"-" + randStr(4)+"-"+ randStr(4)+"-" + randStr(12)
     machine_id = randStr(24)
     
     dataForm = {
          "adid": adid,
          "format": "json",
          "device_id": device_id,
          "email": userFB,
          "password": passFB,
          "generate_analytics_claim": "1",
          "community_id": "",
          "cpl": "true",
          "try_num": "1",
          "family_device_id": device_id,
          "secure_family_device_id":  secure_family_device_id,
          "credentials_type": "password",
          "fb4a_shared_phone_cpl_experiment": "fb4a_shared_phone_nonce_cpl_at_risk_v3",
          "fb4a_shared_phone_cpl_group": "enable_v3_at_risk",
          "enroll_misauth": "false",
          "generate_session_cookies": "1",
          "error_detail_type": "button_with_disabled",
          "source": "login",
          "machine_id": machine_id ,
          "jazoest": "22421",
          "meta_inf_fbmeta": "",
          "advertiser_id": adid,
          "encrypted_msisdn": "",
          "currently_logged_in_userid": "0",
          "locale": "vi_VN",
          "client_country_code": "VN",
          "fb_api_req_friendly_name": "authenticate",
          "fb_api_caller_class": "Fb4aAuthHandler",
          "api_key": "882a8490361da98702bf97a021ddc14d",
          "access_token": "350685531728|62f8ce9f74b12f84c123cc23437a4a32"
     }
    
     dataJson = json.loads(requests.post("https://b-graph.facebook.com/auth/login",data=dataForm, headers=headers).text)
     if (dataJson.get("error") != None):
          if (dataJson["error"]["error_subcode"] == 1348162):
               factor = dataJson["error"]["error_data"]["login_first_factor"]
               uidFB = dataJson["error"]["error_data"]["uid"]
               Get2FA = GetToken2FA(authenticationGG)
               dataForm2Fa = {
                    "adid": adid,
                    "format": "json",
                    "device_id": device_id,
                    "email": userFB,
                    "password": Get2FA,
                    "generate_analytics_claim": "1",
                    "community_id": "",
                    "cpl": "true",
                    "try_num": "2",
                    "family_device_id": device_id,
                    "secure_family_device_id": secure_family_device_id,
                    "sim_serials": "[]",
                    "credentials_type": "two_factor",     
                    "fb4a_shared_phone_cpl_experiment": "fb4a_shared_phone_nonce_cpl_at_risk_v3",
                    "fb4a_shared_phone_cpl_group": "enable_v3_at_risk",
                    "enroll_misauth": "false",
                    "generate_session_cookies": "1",
                    "error_detail_type": "button_with_disabled",
                    "source": "login",
                    "machine_id": machine_id,
                    "jazoest": "22327",
                    "meta_inf_fbmeta": "",
                    "twofactor_code": Get2FA,
                    "userid": uidFB,
                    "first_factor": factor,
                    "advertiser_id": adid,
                    "encrypted_msisdn": "",
                    "currently_logged_in_userid": "0",
                    "locale": "vi_VN",
                    "client_country_code": "VN",
                    "fb_api_req_friendly_name": "authenticate",
                    "fb_api_caller_class": "Fb4aAuthHandler",
                    "api_key": "882a8490361da98702bf97a021ddc14d",                    
                    "access_token": "350685531728|62f8ce9f74b12f84c123cc23437a4a32"
               }
               pass2Fa = json.loads(requests.post("https://b-graph.facebook.com/auth/login",data=dataForm2Fa, headers=headers).text)
               if (pass2Fa.get("error") == None):
                    try:
                         listExportCookies=[]
                         for totalCount in range(len(pass2Fa["session_cookies"])):
                              try:
                                   listExportCookies.append(pass2Fa["session_cookies"][totalCount + 1 - 1]["name"] + "=" + pass2Fa["session_cookies"][totalCount + 1 - 1]["value"] + "; ")
                              except:
                                   break
                         return {
                              "success": {
                                   "setCookies": "".join(listExportCookies),
                                   "accessTokenFB": pass2Fa["access_token"],
                                   "cookiesKey-ValueList": pass2Fa["session_cookies"]
                              }
                         }
                    except:
                         return {
                              "error": {}
                         }
               else:
                    return {
                         "error": {
                              "title": pass2Fa["error"]["error_user_title"],
                              "description": pass2Fa["error"]["error_user_msg"],
                              "error_subcode": pass2Fa["error"]["error_subcode"],
                              "error_code": pass2Fa["error"]["code"],
                              "fbtrace_id": pass2Fa["error"]["fbtrace_id"],
                         }
                    }
          else:
               return {
                         "error": {
                              "title": dataJson["error"]["error_user_title"],
                              "description": dataJson["error"]["error_user_msg"],
                              "error_subcode": dataJson["error"]["error_subcode"],
                              "error_code": dataJson["error"]["code"],
                              "fbtrace_id": dataJson["error"]["fbtrace_id"],
                         }
                    }
     else:
          try:
               listExportCookies=[]
               for totalCount in range(len(dataJson["session_cookies"])):
                    try:
                         listExportCookies.append(dataJson["session_cookies"][totalCount + 1 - 1]["name"] + "=" + dataJson["session_cookies"][totalCount + 1 - 1]["value"] + "; ")
                    except:
                         break
               return {
                    "success": {
                         "setCookies": "".join(listExportCookies),
                         "accessTokenFB": dataJson["access_token"],
                         "cookiesKey-ValueList": dataJson["session_cookies"]
                    }
               }
          finally:
               pass# return dataJson
               
""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):
 
     - userFB: username/phone/gmail Facebook
     - passFB: Mật khẩu Facebook
     - authenticationGG: mã 2fa (nếu có)
     
* Kết quả trả về:
     
     Không có dữ liệu.
     
     - Ghi chú: nếu không hiểu gì hãy ib tui nhé hehe.

* Thông tin tác giả:
     Facebook:  m.me/Booking.MinhHuyDev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Sửa đổi vào thứ vào lúc 02:39 ngày 26/6/2023 • Cập nhật mới nhất: 02:39 26/06/2023
✓Tôn trọng tác giả ❤️
"""