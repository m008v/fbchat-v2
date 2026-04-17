def parse_cookie_string(cookie_string):
     cookie_dict = {}
     cookies = cookie_string.split(";")

     for cookie in cookies:
          if "=" in cookie:
               key, value = cookie.split("=")
               


     return cookie_dict

print(parse_cookie_string("ndpr=1.100000023841858; datr=Mu3YaX2AiRRe-Iah0PN6-Qhl; sb=Mu3YafO0qj0rwVsyBYxmbh-P; locale=vi_VN; ps_l=1; ps_n=1; c_user=9209278; fr=14rLCaKI5L0jzU8wz.AWdzYGk-y4JPZLvJh-e4626mrjjiR_1sZypLx3fEOgDAu-chl8E.Bp37hs..AAA.0.0.Bp37hs.AWcnxDYo8W8LxMqnlfo4pxlispY; xs=44%3AN3mb0w3t9A2ApA%3A2%3A1776269415%3A-1%3A-1%3A%3AAcwUQwKdMfKTgKkXOlsJ1Wa3I39MKL2qKCDRYsmPew; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1776270051645%2C%22v%22%3A1%7D; wd=1517x828"))