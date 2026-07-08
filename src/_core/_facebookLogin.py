import httpx
import string
import random
import re

FB_AUTH_URL = "https://b-graph.facebook.com/auth/login"
TWO_FA_URL = "https://2fa.live/tok/{}"
REQUEST_TIMEOUT = 20
DIRECT_OTP_RE = re.compile(r"^\d{6,8}$")
TWO_FACTOR_SUBCODES = {1348162, 1348023}

"""
Written by Nguyen Minh Huy (RainTee)
Facebook Login V2 - Fixed
Datetime: 28/12/2022
Last Update: 10/06/2026 
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


def _build_proxy(proxies):
     if not proxies:
          return None
     return f"http://{proxies}"

def _post_json(url, data, headers, proxies):
     try:
          proxy = _build_proxy(proxies)
          with httpx.Client(timeout=REQUEST_TIMEOUT, proxy=proxy) as client:
               response = client.post(url, data=data, headers=headers)
          return response.json()
     except (httpx.HTTPError, ValueError) as err:
          return {"error": {"error_user_msg": str(err), "code": -1}}

async def _post_json_async(url, data, headers, proxies):
     try:
          proxy = _build_proxy(proxies)
          async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, proxy=proxy) as client:
               response = await client.post(url, data=data, headers=headers)
          return response.json()
     except (httpx.HTTPError, ValueError) as err:
          return {"error": {"error_user_msg": str(err), "code": -1}}


def _error_result(title, description, *, error_code=-1, error_subcode=None):
     return {
          "error": {
               "title": title,
               "description": description,
               "error_subcode": error_subcode,
               "error_code": error_code,
               "fbtrace_id": None,
          }
     }
         
def _validate_2fa_key(key2Fa):
     """Validate và chuẩn hoá 2FA key. Trả về (token_str, is_direct_otp) hoặc ("", False) nếu rỗng."""
     if key2Fa is None:
          return "", False
     token = str(key2Fa).replace(" ", "").strip()
     if not token:
          return "", False
     if DIRECT_OTP_RE.fullmatch(token):
          return token, True
     return token, False

def GetToken2FA(key2Fa):
     try:
          token, is_direct = _validate_2fa_key(key2Fa)
          if not token or is_direct:
               return token
          with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
               resp = client.get(TWO_FA_URL.format(token))
          return str(resp.json().get("token", "")).strip()
     except (httpx.HTTPError, ValueError, TypeError):
          raise ValueError("Invalid 2FA key provided.")

async def GetToken2FA_async(key2Fa):
     try:
          token, is_direct = _validate_2fa_key(key2Fa)
          if not token or is_direct:
               return token
          async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
               resp = await client.get(TWO_FA_URL.format(token))
          return str(resp.json().get("token", "")).strip()
     except (httpx.HTTPError, ValueError, TypeError):
          raise ValueError("Invalid 2FA key provided.")

class loginFacebook:


     def __init__(self, username, password, AuthenticationGoogleCode=None, proxies=None):
          
          self.deviceID = self.adID = self.secureFamilyDeviceID = f"{randStr(8)}-{randStr(4)}-{randStr(4)}-{randStr(4)}-{randStr(12)}"
          self.manchineID = randStr(24)
          self.usernameFacebook = username # IDFB or email/phone number need login (IDFB hoặc email/sđt cần đăng nhập)
          self.passwordFacebook = password # Password of the account (Mật khẩu của tài khoản)
          self.twoTokenAccess = AuthenticationGoogleCode # string of 16 characters (or more) provided by Facebook (một chuỗi gồm 16 kí tụ (hoặc hơn) được cấp bởi Facebook)
          self.proxies = proxies # Proxy settings for the request (format: ip:port) (Cài đặt proxy cho yêu cầu (định dạng: ip:port))

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
               "User-Agent": "Mozilla/5.0 (Linux; Android 16; V2419A Build/BP2A.250605.031.A3_V000L1) [FBAN/FB4A;FBAV/340.0.0.27.113;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/324485361;FBCR/Viettel Mobile;FBMF/samsung;FBBD/samsung;FBDV/SM-G988N;FBSV/7.1.2;FBCA/x86:armeabi-v7a;FBDM/{density=1.0,width=540,height=960};FB_FW/1;FBRV/0;]",
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
          return _post_json(FB_AUTH_URL, data_form, self._headers(), self.proxies)

     async def _login_async(self, data_form):
          return await _post_json_async(FB_AUTH_URL, data_form, self._headers(), self.proxies)

     def _extract_two_factor_metadata(self, error):
          error_data = error.get("error_data", {}) if isinstance(error, dict) else {}
          user_id = str(
               error_data.get("uid")
               or error_data.get("userid")
               or error_data.get("user_id")
               or ""
          ).strip()
          first_factor = str(
               error_data.get("login_first_factor")
               or error_data.get("first_factor")
               or error_data.get("first_factor_id")
               or ""
          ).strip()
          return user_id, first_factor

     def _build_two_factor_form(self, token_2fa, user_id, first_factor, try_num):
          data_form_2fa = self._base_form(self.passwordFacebook, "two_factor", try_num)
          data_form_2fa["twofactor_code"] = token_2fa
          data_form_2fa["userid"] = user_id
          data_form_2fa["first_factor"] = first_factor
          return data_form_2fa

     def _run_two_factor(self, token_2fa, user_id, first_factor, try_num):
          return self._login(
               self._build_two_factor_form(token_2fa, user_id, first_factor, try_num)
          )

     async def _run_two_factor_async(self, token_2fa, user_id, first_factor, try_num):
          return await self._login_async(
               self._build_two_factor_form(token_2fa, user_id, first_factor, try_num)
          )
          
     def main(self):
          data_form = self._base_form(self.passwordFacebook, "password", 1)
          print(data_form)  # Debug log for form data
          dataJson = self._login(data_form)
          print("Initial login response:", dataJson)  # Debug log for initial response
          error = dataJson.get("error")
          if error is None:
               return jsonResults(dataJson, 1, _build_cookie_export(dataJson.get("session_cookies")))

          error_subcode = error.get("error_subcode")
          if error_subcode not in TWO_FACTOR_SUBCODES:
                return jsonResults(dataJson, 0)

          try:
               token_2fa = GetToken2FA(self.twoTokenAccess)
          except ValueError as err:
               return _error_result("Invalid 2FA key", str(err), error_code=-2)

          if not token_2fa:
               return _error_result(
                    "Missing 2FA token",
                    "Facebook yêu cầu 2FA nhưng AuthenticationGoogleCode đang trống.",
                    error_code=-2,
                    error_subcode=error_subcode,
               )

          user_id, first_factor = self._extract_two_factor_metadata(error)
          if not user_id or not first_factor:
               return _error_result(
                    "Missing 2FA metadata",
                    "Facebook không trả về đủ `uid` hoặc `login_first_factor` để hoàn tất bước 2FA.",
                    error_code=-3,
                    error_subcode=error_subcode,
               )

          pass2Fa = self._run_two_factor(token_2fa, user_id, first_factor, 2)
          if pass2Fa.get("error") is not None:
               is_direct_otp = DIRECT_OTP_RE.fullmatch(
                    str(self.twoTokenAccess or "").replace(" ", "").strip()
               )
               if not is_direct_otp:
                    retry_token = GetToken2FA(self.twoTokenAccess)
                    if retry_token and retry_token != token_2fa:
                         retry_response = self._run_two_factor(
                              retry_token,
                              user_id,
                              first_factor,
                              3,
                         )
                         if retry_response.get("error") is None:
                              return jsonResults(
                                   retry_response,
                                   1,
                                   _build_cookie_export(retry_response.get("session_cookies")),
                              )
               return jsonResults(pass2Fa, 0)

          return jsonResults(pass2Fa, 1, _build_cookie_export(pass2Fa.get("session_cookies")))

     async def main_async(self):
          """Async version của main() — toàn bộ flow login chạy non-blocking."""
          data_form = self._base_form(self.passwordFacebook, "password", 1)
          dataJson = await self._login_async(data_form)
          error = dataJson.get("error")
          if error is None:
               return jsonResults(dataJson, 1, _build_cookie_export(dataJson.get("session_cookies")))

          error_subcode = error.get("error_subcode")
          if error_subcode not in TWO_FACTOR_SUBCODES:
                return jsonResults(dataJson, 0)

          try:
               token_2fa = await GetToken2FA_async(self.twoTokenAccess)
          except ValueError as err:
               return _error_result("Invalid 2FA key", str(err), error_code=-2)

          if not token_2fa:
               return _error_result(
                    "Missing 2FA token",
                    "Facebook yêu cầu 2FA nhưng AuthenticationGoogleCode đang trống.",
                    error_code=-2,
                    error_subcode=error_subcode,
               )

          user_id, first_factor = self._extract_two_factor_metadata(error)
          if not user_id or not first_factor:
               return _error_result(
                    "Missing 2FA metadata",
                    "Facebook không trả về đủ `uid` hoặc `login_first_factor` để hoàn tất bước 2FA.",
                    error_code=-3,
                    error_subcode=error_subcode,
               )

          pass2Fa = await self._run_two_factor_async(token_2fa, user_id, first_factor, 2)
          if pass2Fa.get("error") is not None:
               is_direct_otp = DIRECT_OTP_RE.fullmatch(
                    str(self.twoTokenAccess or "").replace(" ", "").strip()
               )
               if not is_direct_otp:
                    retry_token = await GetToken2FA_async(self.twoTokenAccess)
                    if retry_token and retry_token != token_2fa:
                         retry_response = await self._run_two_factor_async(
                              retry_token,
                              user_id,
                              first_factor,
                              3,
                         )
                         if retry_response.get("error") is None:
                              return jsonResults(
                                   retry_response,
                                   1,
                                   _build_cookie_export(retry_response.get("session_cookies")),
                              )
               return jsonResults(pass2Fa, 0)

          return jsonResults(pass2Fa, 1, _build_cookie_export(pass2Fa.get("session_cookies")))


"""
✓Remake by Nguyễn Minh Huy
✓Tôn trọng tác giả ❤️
"""

if __name__ == "__main__":
    import os
    # Usage: FBCHAT_USER=xxx FBCHAT_PASS=xxx FBCHAT_2FA=xxx python _facebookLogin.py
    user = os.environ.get("FBCHAT_USER")
    pwd = os.environ.get("FBCHAT_PASS")
    code = os.environ.get("FBCHAT_2FA")
    if not all([user, pwd]):
        print("Set FBCHAT_USER and FBCHAT_PASS env vars")
        raise SystemExit(1)
    print(loginFacebook(user, pwd, code).main())
