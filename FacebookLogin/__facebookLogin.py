try:
 import requests
 import re
 import json
 from bs4 import BeautifulSoup as BS
except:
 exit("\033[1;92mPYTHON LIBRARY\033[1;97m: THIẾU ĐẦU VÀO!")

#this code was written in 4/2022, Facebook can edit the login in a different way!

def setHeaders(cookies):
  headers={}
  headers["Host"] = "m.facebook.com";
  headers["origin"] = "https://m.facebook.com";
  headers["content-type"] = "application/x-www-form-urlencoded";
  headers["user-agent"] = "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36";
  headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9";
  headers["sec-fetch-site"] = "same-origin";
  headers["sec-fetch-mode"] = "navigate";
  headers["sec-fetch-user"] = "?1";
  headers["sec-fetch-dest"] = "document";
  headers["referer"] = "https://m.facebook.com/login/?";
  headers["accept-encoding"] = "gzip, deflate"
  headers["accept-language"] = "en-US,en;q=0.9";
  headers["x-requested-with"] = "mark.via.gp";
  headers["cookie"] = cookies;
  return headers;
def Login(User,Pass,Two_code):

 headers = {};
 headers["Host"] = "m.facebook.com";
 headers["origin"] = "https://m.facebook.com";
 headers["content-type"] = "application/x-www-form-urlencoded";
 headers["user-agent"] = "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36";
 headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9";
 headers["sec-fetch-site"] = "same-origin";
 headers["sec-fetch-mode"] = "navigate";
 headers["sec-fetch-user"] = "?1";
 headers["sec-fetch-dest"] = "document";
 headers["referer"] = "https://m.facebook.com/login/?";
 headers["accept-encoding"] = "gzip, deflate";
 headers["x-requested-with"] = "mark.via.gp";
 headers["accept-language"] = "en-US,en;q=0.9";
  
 ajax = requests.Session()
 homeLogin = ajax.get(
 "https://m.facebook.com/login/?",
 headers = headers
 ).text
 cookies = ajax.cookies.get_dict()
 try:
      
      aJax = requests.Session()
      
      datr = cookies["datr"]
      sb = cookies["sb"]
      cookies = f"datr={datr};sb={sb};";
      
      
      headers = setHeaders(cookies)
      
      postForm = {};
      postForm["lsd"] = homeLogin.split('"LSD",[],{"token":"')[1].split('"}')[0]
      postForm["jazoest"] = homeLogin.split('type="hidden" name="jazoest" value="')[1].split('" autocomplete="off" />')[0];
      postForm["m_ts"] = homeLogin.split('type="hidden" name="m_ts" value="')[1].split('" />')[0]
      postForm["li"] = homeLogin.split('type="hidden" name="li" value="')[1].split('" />')[0]
      postForm["try_number"] = "0";
      postForm["unrecognized_tries"] = "0";
      postForm["email"] = User;
      postForm["pass"] = Pass;
      postForm["login"] = "Log In";
      postForm["prefill_contact_point"] = User;
      postForm["prefill_source"] = "browser_dropdown";
      postForm["prefill_type"] = "password";
      postForm["first_prefill_source"] = "browser_dropdown";
      postForm["first_prefill_type"] = "contact_point";
      postForm["had_cp_prefilled"] = "false";
      postForm["had_password_prefilled"] = "false";
      postForm["is_smart_lock"] = "false";
      postForm["bi_xrwh"] = homeLogin.split('id="bi_xrwh" name="bi_xrwh" value="')[1].split('" />')[0];
      postForm["bi_wvdp"] = '{"hwc":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false,"iframeProto":"function get contentWindow() { [native code] }","remap":false,"iframeData":{"hwc":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false}}';
      
      postRequests = aJax.post(
      "https://m.facebook.com/login/device-based/regular/login/?refsrc=deprecated&lwv=100&ref=nmh3010",
      headers = headers,
      data = postForm
      )
      try:
       try:
        #login 2fa
        checkpoint = aJax.cookies.get_dict()["checkpoint"]
        datr = aJax.cookies.get_dict()["datr"]
        fr = aJax.cookies.get_dict()["fr"]
        setCookies = f"fr={fr}; wd=393x733; checkpoint={checkpoint}; datr={datr}; x-referer=; locale=vi_VN; dpr=2.75; m_pixel_ratio=2.75;"
        post2Fa = requests.get(
        "https://m.facebook.com/checkpoint/?",
         headers={"cookie": setCookies}
        )
        SoupBS = BS(post2Fa.text, 'html.parser')
        match (SoupBS.title.text):
        
         case "Nhập mã đăng nhập để tiếp tục":
          setCookies=f"checkpoint={aJax.cookies.get_dict()['checkpoint']}; datr={aJax.cookies.get_dict()['datr']}; fr={aJax.cookies.get_dict()['fr']}; locate={aJax.cookies.get_dict()['locate']}"
          print("\033[1;92m]FACEBOOK LOGIN\033[1;97m: ĐĂNG NHẬP THÀNH CÔNG! TIẾN HÀNH VƯỢT 2FA!")
          print("\033[1;93mFACEBOOK LOGIN\033[1;97m: TIẾN HÀNH LẤY MÃ 2FA")
          try:
           twofaCode = json.loads(requests.get("https://2fa.live/tok/"+str(Two_code)).text)["token"]
           print("\033[1;92mFACEBOOK LOGIN\033[1;97m: THÀNH CÔNG! TIẾN HÀNH NHẬP 2FA")
          except:
           print("\033[1;91mFACEBOOK LOGIN\033[1;97m: DỮ LIỆU 2FA KHÔNG HỢP LỆ!")
           exit;
          postForm = {}
          postForm["fb_dtsg"] = post2Fa.text.split('name="fb_dtsg" value="')[1].split('"')[0];
          postForm["jazoest"] = post2Fa.text.split('name="jazoest" value="')[1].split('"')[0];
          postForm["checkpoint_data"] = "";
          postForm["approvals_code"] = twofaCode;
          postForm["codes_submitted"] = "0";
          postForm["submit[Submit Code]"] = "";
          postForm["nh"] = post2Fa.text.split('name="nh" value="')[1].split('"')[0];
          Over2FaRequests = requests.Session()
          Over2Fa = Over2FaRequests.post(
          "https://m.facebook.com/login/checkpoint/?next=https%3A%2F%2Fm.facebook.com%2Fhome.php",
          headers={"origin": "https://m.facebook.com","x-requested-with": "mark.via.gp","user-agent": "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36","referer": "https://mfacebook.com/login/checkpoint/next?","cookie": setCookies},
          data=postForm
          )
          #print(Over2FaRequests.cookies.get_dict())
          #z = open("data.json","w").write(str(Over2Fa.text))
          home2Fa = BS(Over2Fa.text, 'html.parser')
          match (home2Fa.title.text):
           case "Nhớ trình duyệt":
            setCookies = f"checkpoint={Over2FaRequests.cookies.get_dict()['checkpoint']}; sfiu=; fr={Over2FaRequests.cookies.get_dict()['fr']}; wd=393x733; x-referer=; locale=vi_VN; dpr=2.75; m_pixel_ratio=2.75; sb=; datr={datr};"
            #print(setCookies)
            print("\033[1;92mFACEBOOK LOGIN\033[1;97m: VƯỢT 2FA THÀNH CÔNG! BẮT ĐẦU `setCookies` và `rememberBrowser`")
            postForm = {}
            postForm["fb_dtsg"] = post2Fa.text.split('name="fb_dtsg" value="')[1].split('"')[0];
            postForm["jazoest"] = post2Fa.text.split('name="jazoest" value="')[1].split('"')[0];
            postForm["name_action_selected"] = "dont_save";
            postForm["submit[Continue]"] = "Tiếp tục";
            postForm["nh"] = post2Fa.text.split('name="nh" value="')[1].split('"')[0];
            setCookiesRequests = requests.Session()
            rememberBrowser = setCookiesRequests.post(
            "https://m.facebook.com/login/checkpoint/?ref=dbl",
            headers={"origin": "https://m.facebook.com","x-requested-with": "mark.via.gp","user-agent": "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36","referer": "https://m.facebook.com/login/checkpoint/?ref=dbl","cookie": setCookies},
            data=postForm
            )
            print(rememberBrowser.text)
            cofirmVượt2Fa = BS(rememberBrowser.text, 'html.parser')
            match (cofirmVượt2Fa.title.text):
             case "Xem lại lần đăng nhập gần đây":
              print("\033[1;93mFACEBOOK LOGIN\033[1;97m: TIẾN HÀNH XÁC NHẬN `ĐÂY LÀ TÔI`\033[0m")
              postForm = {}
              postForm["fb_dtsg"] = post2Fa.text.split('name="fb_dtsg" value="')[1].split('"')[0];
              postForm["jazoest"] = post2Fa.text.split('name="nh" value="')[1].split('"')[0];
              postForm["checkpoint_data"] = "";
              postForm["submit[Continue]"] = "Tiếp tục";
              postForm["nh"] = post2Fa.text.split('name="nh" value="')[1].split('"')[0];
              dameHomeRequests = requests.Session()
              dataHome = dameHomeRequests.post(
              "https://m.facebook.com/login/checkpoint/",
              headers={"origin": "https://m.facebook.com","x-requested-with": "mark.via.gp","user-agent": "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36","referer": "https://m.facebook.com/login/checkpoint/?ref=dbl","cookie": setCookies},
              data=postForm
              )
              thiswayMerequests = requests.Session()
              postForm = {}
              postForm["fb_dtsg"] = dataHome.text.split('name="fb_dtsg" value="')[1].split('"')[0];
              postForm["jazoest"] = dataHome.text.split('name="jazoest" value="')[1].split('"')[0];
              postForm["checkpoint_data"] = "";
              postForm["submit[This was me]"] = "This was me";
              postForm["nh"] = dataHome.text.split('name="nh" value="')[1].split('"')[0];
              thisWayMe = thiswayMerequests.post(
              "https://m.facebook.com/login/checkpoint/",
              headers={"origin": "https://m.facebook.com","x-requested-with": "mark.via.gp","user-agent": "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36","referer": "https://m.facebook.com/login/checkpoint/?ref=dbl","cookie": setCookies},
              data=postForm
              )
              twMbS = BS(thisWayMe.text, 'html.parser')
              match (twMbS.title.text):
               case "Nhớ trình duyệt":
                #setCookies = f"fr={thiswayMerequests.cookies.get_dict()['fr']}; wd=393x733; checkpoint={thiswayMerequests.cookies.get_dict()['checkpoint']}; datr={datr}; x-referer=; locale=vi_VN; dpr=2.75; m_pixel_ratio=2.75;"
                postForm = {}
                postForm["fb_dtsg"] = thisWayMe.text.split('name="fb_dtsg" value="')[1].split('"')[0];
                postForm["jazoest"] = thisWayMe.text.split('name="jazoest" value="')[1].split('"')[0];
                postForm["checkpoint_data"] = "";
                postForm["name_action_selected"] = "save_device";
                postForm["submit[Continue]"] = "Tiếp tục";
                postForm["nh"] = thisWayMe.text.split('name="nh" value="')[1].split('"')[0];
                continueCofirmRequests = requests.Session()
                continueCofirm = continueCofirmRequests.post(
                "https://m.facebook.com/login/checkpoint/",
                headers={"origin": "https://m.facebook.com","x-requested-with": "mark.via.gp","user-agent": "Mozilla/5.0 (Linux; Android 11; M2101K7BG Build/RP1A.200720.011;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.79 Mobile Safari/537.36","referer": "https://m.facebook.com/home.php","cookie": setCookies},
                data=postForm
                )
                R = BS(continueCofirm.text, 'html.parser')
                return exit(f"DatabaseError: `{R.title.text}`")
                
               case _:
                print("\033[1;91m-> FACEBOOK LOGIN <-\033[1;97m XÁC NHẬN THẤT BẠI! THỬ LẠI SAU.")
                exit;
              return exit("\033[0mTypeError: ")
             case _:
              pass
           case _:
            print("\033[1;93mFACEBOOK LOGIN\033[1;97m: VƯỢT 2FA KHÔNG THÀNH CÔNG! KIỂM TRA MÃ 2FA VÀ THỬ LẠI SAU")
            return {
             "dataSendStatus": "error",
             "error": "Couldn't login. Facebook might have blocked this account. Please login with a browser or enable the option 'forceLogin' and try again.",
             "errcode": 404
            }
         case "Cần phê duyệt đăng nhập":
              setCookies=f"checkpoint={aJax.cookies.get_dict()['checkpoint']}; datr={aJax.cookies.get_dict()['datr']}; fr={aJax.cookies.get_dict()['fr']}; locate=vi_VN;"
              return {
               "dataSendStatus": "error",
               "error": "Please check the login information below. Is that you?.",
               "errcode": 500
              }
         case _:
          print("\033[1;93mFACEBOOK LOGIN\033[1;97m: ĐĂNG NHẬP KHÔNG THÀNH CÔNG HOẶC XẢY RA LỖI!")
          return {
           "dataSendStatus": "error",
           "error": "Couldn't login. Facebook might have blocked this account. Please login with a browser or enable the option 'forceLogin' and try again.",
           "errcode": 404
          }
          exit;
       except:
        formHome = BS(postRequests.text, 'html.parser')
        match (formHome.title.text):
         case "Log in to Facebook | Facebook":
          print("\033[1;93mFACEBOOK LOGIN\033[1;97m: KIỂM TRA LẠI TÀI KHOẢN HOẶC MẬT KHẨU.")
          return {
           "dataSendStatus": "error",
           "error": "Invalid account or password. Please try again later."
          }
         case _:
          setCookies = f"datr={aJax.cookies.get_dict()['datr']}; fr={aJax.cookies.get_dict()['fr']}; locale=vi_VN; wd=393x733; xs={aJax.cookies.get_dict()['xs']}; c_user={aJax.cookies.get_dict()['c_user']}; dpr=2.75; m_pixel_ratio=2.75; sb={aJax.cookies.get_dict()['sb']};"
          return {
           "setCookies": setCookies,
           "botID": aJax.cookies.get_dict()['c_user'],
           "statusCode": 302,
           "dataSendStatus": "success",
           "browerSave": True
          }
          print(BS(z.text, 'html.parser').text)
        
      except:
       return {
        "dataSendStatus": "error",
        "error": "Couldn't login. Facebook might have blocked this account. Please login with a browser or enable the option 'forceLogin' and try again.",
        "errcode": 404
       }
 except:
  return print("\033[1;91mFACEBOOK LOGIN\033[1;97m: LỖI KẾT NỐI CƠ SỞ DỮ LIỆU `FACEBOOK`")
  
# print(Login("nhập user/gmail fb","pass fb",""))
