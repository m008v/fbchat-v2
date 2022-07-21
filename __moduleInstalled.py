import os
class Python():
 def Installed():
  installedList=['lxml','fbchat','uuid','my_fake_useragent','py-cpuinfo','speedtest-cli','pycurl','pystyle','requests-cache','requests-html','requests_futures','requests','youtube-search-python','beautifulsoup4','google','cloudflare','datetime','colorama','flask','flask_restful']
  print("\033[1;93mPYTHON LIBRARY\033[1;97m: KHÔNG TÌM THẤY MODULE , TIẾN HÀNH TẢI XUỐNG")
  print("\033[1;92mPYTHON LIBRARY\033[1;97m: ĐANG KIỂM TRA CẬP NHẬT PHIÊN BẢN\033[0m")
  os.system("pip install --upgrade pip")
  os.system("apt-get update")
  os.system("apt upgrade")
  for i in range(int(len(installedList)+1)):
   try:
    print("\033[1;93mPYTHON LIBRARY\033[1;97m: Tiến hành cài đặt `"+str(installedList[i+1-1])+"`\033[0m")
    os.system("pip install " + installedList[i+1-1])
   except:
    exit("\033[1;92mPYTHON LIBRARY\033[1;97m: Mọi thứ đã cài đặt thành công! TRẢI NGHIỆM NGAY.")
   
#Python.Installed()
