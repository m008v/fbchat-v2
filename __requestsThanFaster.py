try:
    import requests
    from requests.sessions import Session
    from threading import Thread,local
    from concurrent.futures import ThreadPoolExecutor
except ImportError:
    raise SystemExit("Please install requests package")

# remake source code from stackoverflow (https://stackoverflow.com/questions/62599036/python-requests-is-slow-and-takes-very-long-to-complete-http-or-https-request)
# AUTHOR: MinhHuyDev (https://github.com/MinhHuyDev)
# Notes: sorry, I just have my hands free to write GET & POST code. If you are a programmer or have a bit of experience in coding, you can write the rest yourself like 'GET'
thread_local = local()
class Requests():
    def getSessionRequests() -> Session:
        if not hasattr(thread_local,'session'):
            thread_local.session = requests.Session()
        return thread_local.session
    

    # GET: 16/08/2022 03:17 PM (GMT + 7)
    def GET(url:str, headers, proxies:str, allow_redirects=False, timeout=30, verify=True):
 
      session = Requests.getSessionRequests()
      session.proxies = proxies;
      session.allow_redirects = allow_redirects;
      session.verify = verify;
      session.timeout = timeout;

      with session.get(url, headers=headers) as response:
          return {
            "results": {
                "contentsWebsite": response.text,
                "statusCode": response.status_code,
                "urlLocate": response.url,
                "headersResponse": response.headers,
                "cookiesResponse": response.cookies,
                "encodeResponse": response.encoding,
                "timeRequests": response.elapsed.total_seconds(),
                "redirectPremanent": response.is_permanent_redirect
            }
          }
    # POST: 17/08/2022 01:42 AM (GMT + 7)
    def POST(url:str, headers, data, proxies, allow_redirects=False, timeout=30, verify=True):
      
      session = Requests.getSessionRequests()
      session.proxies = proxies;
      session.allow_redirects = allow_redirects;
      session.verify = verify;
      session.timeout = timeout;

      with session.post(url, headers=headers, data=data) as response:
          return {
            "results": {
                "contentsWebsite": response.text,
                "statusCode": response.status_code,
                "urlLocate": response.url,
                "headersResponse": response.headers,
                "cookiesResponse": response.cookies,
                "encodeResponse": response.encoding,
                "timeRequests": response.elapsed.total_seconds(),
                "redirectPremanent": response.is_permanent_redirect
            }
          }


# while True:
#     var = Requests.GET("https://api.minhhuy.dev/docs/?verify=true", {}, "")
#     print(var["results"]["contentsWebsite"])