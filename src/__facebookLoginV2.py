import requests
import re
import string
import random
import json

"""
Written by Nguyen Minh Huy (RainTee)
Facebook Login V2 - Fixed
Dstetime: 28/12/2022
Last Update: 04/08/2023 
"""

def jsonResults(dataJson, statusLogin, listExportCookies=None):
     if (statusLogin == 1):
          return {
               "success": {
                    "setCookies": "".join(listExportCookies),
                    "accessTokenFB": dataJson["access_token"],
                    "cookiesKey-ValueList": dataJson["session_cookies"]
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
               
def randStr(length):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
         
def GetToken2FA(key2Fa):
     try:
          twoFARequests = json.loads(requests.get("https://2fa.live/tok/" + key2Fa.replace(" ","")).text)
          return twoFARequests["token"] 
     except:
          return random.randint(100000, 999999) # TROLL TIME (appears only when it has an error) ¯⁠\⁠_⁠(⁠ツ⁠)⁠_⁠/⁠¯

class loginFB:


     def __init__(self, username, password, AuthenticationGoogleCode=None):
          
          self.deviceID = self.adID = self.secureFamilyDeviceID = f"{randStr(8)}-{randStr(4)}-{randStr(4)}-{randStr(4)}-{randStr(12)}"
          self.manchineID = randStr(24)
          self.usernameFacebook = username # IDFB or email/phone number need login (IDFB hoặc email/sđt cần đăng nhập)
          self.passwordFacebook = password # Password of the account (Mật khẩu của tài khoản)
          self.twoTokenAccess = AuthenticationGoogleCode # string of 16 characters (or more) provided by Facebook (một chuỗi gồm 16 kí tụ (hoặc hơn) được cấp bởi Facebook)
          
          """
          Note: 
               - English: If you don't have two-factor authentication set up, you can skip it.
               - Vietnamese: Nếu bạn không thiết lập xác thực hai yếu tố, bạn có thể bỏ qua nó.
          """
          
     def main(self):
          
          headers = {}
          headers["Host"] = "b-graph.facebook.com"
          headers["Content-Type"] = "application/x-www-form-urlencoded"
          headers["X-Fb-Connection-Type"] = "unknown"
          headers["User-Agent"] = "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G988N Build/NRD90M) [FBAN/FB4A;FBAV/340.0.0.27.113;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/324485361;FBCR/Viettel Mobile;FBMF/samsung;FBBD/samsung;FBDV/SM-G988N;FBSV/7.1.2;FBCA/x86:armeabi-v7a;FBDM/{density=1.0,width=540,height=960};FB_FW/1;FBRV/0;]"
          headers["X-Fb-Connection-Quality"] = "EXCELLENT"
          headers["Authorization"] = "OAuth null"
          headers["X-Fb-Friendly-Name"] = "authenticate"
          headers["Accept-Encoding"] = "gzip, deflate"
          headers["X-Fb-Server-Cluster"] = "True"

          
          dataForm = {}
          dataForm["adid"] = self.adID
          dataForm["format"] = "json"
          dataForm["device_id"] = self.deviceID
          dataForm["email"] = self.usernameFacebook
          dataForm["password"] = self.passwordFacebook
          dataForm["generate_analytics_claim"] = "1"
          dataForm["community_id"] = ""
          dataForm["cpl"] = "true"
          dataForm["try_num"] = "1"
          dataForm["family_device_id"] = self.deviceID
          dataForm["secure_family_device_id"] = self.secureFamilyDeviceID
          dataForm["credentials_type"] = "password"
          dataForm["fb4a_shared_phone_cpl_experiment"] = "fb4a_shared_phone_nonce_cpl_at_risk_v3"
          dataForm["fb4a_shared_phone_cpl_group"] = "enable_v3_at_risk"
          dataForm["enroll_misauth"] = "false"
          dataForm["generate_session_cookies"] = "1"
          dataForm["error_detail_type"] = "button_with_disabled"
          dataForm["source"] = "login"
          dataForm["machine_id"] = self.manchineID
          dataForm["jazoest"] = "22421"
          dataForm["meta_inf_fbmeta"] = ""
          dataForm["advertiser_id"] = self.adID
          dataForm["encrypted_msisdn"] = ""
          dataForm["currently_logged_in_userid"] = "0"
          dataForm["locale"] = "vi_VN"
          dataForm["client_country_code"] = "VN"
          dataForm["fb_api_req_friendly_name"] = "authenticate"
          dataForm["fb_api_caller_class"] = "Fb4aAuthHandler"
          dataForm["api_key"] = "882a8490361da98702bf97a021ddc14d"
          dataForm["access_token"] = "350685531728|62f8ce9f74b12f84c123cc23437a4a32"

         
          dataJson = json.loads(requests.post("https://b-graph.facebook.com/auth/login",data=dataForm, headers=headers).text)
          if (dataJson.get("error") != None):
               if (dataJson["error"]["error_subcode"] == 1348162):
                    Get2FA = GetToken2FA(self.twoTokenAccess)
                    dataForm2Fa = {}
                    dataForm2Fa["adid"] = self.adID
                    dataForm2Fa["format"] = "json"
                    dataForm2Fa["device_id"] = self.deviceID
                    dataForm2Fa["email"] = self.usernameFacebook
                    dataForm2Fa["password"] = Get2FA
                    dataForm2Fa["generate_analytics_claim"] = "1"
                    dataForm2Fa["community_id"] = ""
                    dataForm2Fa["cpl"] = "true"
                    dataForm2Fa["try_num"] = "2"
                    dataForm2Fa["family_device_id"] = self.deviceID
                    dataForm2Fa["secure_family_device_id"] = self.secureFamilyDeviceID
                    dataForm2Fa["sim_serials"] = "[]"
                    dataForm2Fa["credentials_type"] = "two_factor"
                    dataForm2Fa["fb4a_shared_phone_cpl_experiment"] = "fb4a_shared_phone_nonce_cpl_at_risk_v3"
                    dataForm2Fa["fb4a_shared_phone_cpl_group"] = "enable_v3_at_risk"
                    dataForm2Fa["enroll_misauth"] = "false"
                    dataForm2Fa["generate_session_cookies"] = "1"
                    dataForm2Fa["error_detail_type"] = "button_with_disabled"
                    dataForm2Fa["source"] = "login"
                    dataForm2Fa["machine_id"] = self.manchineID
                    dataForm2Fa["jazoest"] = "22327"
                    dataForm2Fa["meta_inf_fbmeta"] = ""
                    dataForm2Fa["twofactor_code"] = Get2FA
                    dataForm2Fa["userid"] = dataJson["error"]["error_data"]["uid"]
                    dataForm2Fa["first_factor"] = dataJson["error"]["error_data"]["login_first_factor"]
                    dataForm2Fa["advertiser_id"] = self.adID
                    dataForm2Fa["encrypted_msisdn"] = ""
                    dataForm2Fa["currently_logged_in_userid"] = "0"
                    dataForm2Fa["locale"] = "vi_VN"
                    dataForm2Fa["client_country_code"] = "VN"
                    dataForm2Fa["fb_api_req_friendly_name"] = "authenticate"
                    dataForm2Fa["fb_api_caller_class"] = "Fb4aAuthHandler"
                    dataForm2Fa["api_key"] = "882a8490361da98702bf97a021ddc14d"
                    dataForm2Fa["access_token"] = "350685531728|62f8ce9f74b12f84c123cc23437a4a32"
                    pass2Fa = json.loads(requests.post("https://b-graph.facebook.com/auth/login",data=dataForm2Fa, headers=headers).text)
                    if (pass2Fa.get("error") == None):
                         try:
                              listExportCookies = []
                              for cookie in pass2Fa.get("session_cookies", []):
                                   try:
                                        listExportCookies.append(f"{cookie['name']}={cookie['value']}; ")
                                   except KeyError:
                                        break

                              return dataJson(pass2Fa, 1, listExportCookies)
                         except Exception as errLog:
                              return {"error": {"description": str(errLog)}}
                    else:
                         return jsonResults(pass2Fa, 0)
               else:
                    return jsonResults(dataJson, 0)
          else:
               try:
                    listExportCookies=[]
                    for totalCount in range(len(dataJson["session_cookies"])):
                         try:
                              listExportCookies.append(dataJson["session_cookies"][totalCount + 1 - 1]["name"] + "=" + dataJson["session_cookies"][totalCount + 1 - 1]["value"] + "; ")
                         except:
                              break
                    return jsonResults(dataJson, 1, listExportCookies)
               finally:
                    pass# return dataJson


"""
✓Remake by Nguyễn Minh Huy
✓Sửa đổi mới nhất vào thứ vào lúc 7:56 05/08/2023
✓Tôn trọng tác giả ❤️
"""
