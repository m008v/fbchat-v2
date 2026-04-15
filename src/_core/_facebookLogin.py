import requests
import string
import random
import pyotp

FB_AUTH_URL = "https://b-graph.facebook.com/auth/login"
TWO_FA_URL = "https://2fa.live/tok/{}"
REQUEST_TIMEOUT = 20

"""
Written by Nguyen Minh Huy (RainTee)
Facebook Login V2 - Fixed
Dstetime: 28/12/2022
Last Update: 04/08/2023 
"""

def jsonResults(dataJson, statusLogin, listExportCookies=None):
     payload = dataJson if isinstance(dataJson, dict) else {}
     cookies = listExportCookies or []

     if statusLogin == 1:
          return {
               "success": {
                    "setCookies": "".join(cookies),
                    "accessTokenFB": payload.get("access_token", ""),
                    "cookiesKey-ValueList": payload.get("session_cookies", []),
               }
          }

     error_data = payload.get("error") or {}
     return {
          "error": {
               "title": error_data.get("error_user_title") or "Login failed",
               "description": error_data.get("error_user_msg") or "Unknown error",
               "error_subcode": error_data.get("error_subcode"),
               "error_code": error_data.get("code"),
               "fbtrace_id": error_data.get("fbtrace_id"),
          }
     }
               
def randStr(length):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _build_cookie_export(session_cookies):
     exported = []
     for cookie in session_cookies or []:
          name = cookie.get("name")
          value = cookie.get("value")
          if name is None or value is None:
               continue
          exported.append(f"{name}={value}; ")
     return exported


def _post_json(url, data, headers):
     try:
          response = requests.post(url, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
          return response.json()
     except (requests.RequestException, ValueError) as err:
          return {"error": {"error_user_msg": str(err), "code": -1}}
         
def GetToken2FA(key2Fa):
     try:
          if not key2Fa:
               return ""
          twoFARequests = pyotp.TOTP(key2Fa.replace(" ", "")).now()
          return str(twoFARequests)
     except (requests.RequestException, ValueError, TypeError):
          return str(random.randint(100000, 999999))

class loginFacebook:


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

     def _headers(self):
          return {
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

     def _base_form(self, password, credentials_type, try_num):
          data = {
               "adid": self.adID,
               "format": "json",
               "device_id": self.deviceID,
               "email": self.usernameFacebook,
               "password": password,
               "generate_analytics_claim": "1",
               "community_id": "",
               "cpl": "true",
               "try_num": str(try_num),
               "family_device_id": self.deviceID,
               "secure_family_device_id": self.secureFamilyDeviceID,
               "credentials_type": credentials_type,
               "fb4a_shared_phone_cpl_experiment": "fb4a_shared_phone_nonce_cpl_at_risk_v3",
               "fb4a_shared_phone_cpl_group": "enable_v3_at_risk",
               "enroll_misauth": "false",
               "generate_session_cookies": "1",
               "error_detail_type": "button_with_disabled",
               "source": "login",
               "machine_id": self.manchineID,
               "meta_inf_fbmeta": "",
               "advertiser_id": self.adID,
               "encrypted_msisdn": "",
               "currently_logged_in_userid": "0",
               "locale": "vi_VN",
               "client_country_code": "VN",
               "fb_api_req_friendly_name": "authenticate",
               "fb_api_caller_class": "Fb4aAuthHandler",
               "api_key": "882a8490361da98702bf97a021ddc14d",
               "access_token": "350685531728|62f8ce9f74b12f84c123cc23437a4a32",
          }
          data["jazoest"] = "22421" if credentials_type == "password" else "22327"
          if credentials_type == "two_factor":
               data["sim_serials"] = "[]"
          return data

     def _login(self, data_form):
          return _post_json(FB_AUTH_URL, data_form, self._headers())
          
     def main(self):
          data_form = self._base_form(self.passwordFacebook, "password", 1)
          dataJson = self._login(data_form)

          error = dataJson.get("error")
          if error is None:
               return jsonResults(dataJson, 1, _build_cookie_export(dataJson.get("session_cookies")))

          if error.get("error_subcode") != 1348162:
               return jsonResults(dataJson, 0)

          token_2fa = GetToken2FA(self.twoTokenAccess)
          data_form_2fa = self._base_form(token_2fa, "two_factor", 2)
          error_data = error.get("error_data", {})
          data_form_2fa["twofactor_code"] = token_2fa
          data_form_2fa["userid"] = error_data.get("uid", "")
          data_form_2fa["first_factor"] = error_data.get("login_first_factor", "")

          pass2Fa = self._login(data_form_2fa)
          if pass2Fa.get("error") is not None:
               return jsonResults(pass2Fa, 0)

          return jsonResults(pass2Fa, 1, _build_cookie_export(pass2Fa.get("session_cookies")))



"""
✓Remake by Nguyễn Minh Huy
✓Tôn trọng tác giả ❤️
"""
