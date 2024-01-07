import attr, re, json, random, string, time
from os.path import basename
from mimetypes import guess_type 

def Headers(setCookies, dataForm=None, Host=None):
     if (Host == None): Host = "www.facebook.com"
     headers = {}
     headers["Host"] = Host
     headers["Connection"] = "keep-alive"
     if (dataForm != None):
          headers["Content-Length"] = str(len(dataForm))
     headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
     headers["Accept"] = "*/*"
     headers["Origin"] = "https://" + Host
     headers["Sec-Fetch-Site"] = "same-origin"
     headers["Sec-Fetch-Mode"] = "cors"
     headers["Sec-Fetch-Dest"] = "empty"
     headers["Referer"] = "https://" + Host
     headers["Accept-Language"] = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
     
     return headers
     
def digitToChar(digit):
          if digit < 10:
               return str(digit)
          return chr(ord("a") + digit - 10)

def str_base(number, base):
     if number < 0:
          return "-" + str_base(-number, base)
     (d, m) = divmod(number, base)
     if d > 0:
          return str_base(d, base) + digitToChar(m)
     return digitToChar(m)

def parse_cookie_string(cookie_string):
     cookie_dict = {}
     cookies = cookie_string.split(";")

     for cookie in cookies:
          if "=" in cookie:
               key, value = cookie.split("=")
          else:
               pass
          try: cookie_dict[key] = value
          except: pass

     return cookie_dict

def dataSplit(string1, string2, numberSplit1=None, numberSplit2=None, HTML=None, amount=None, string3=None, numberSplit3=None, defaultValue=None):
     if (defaultValue): numberSplit1, numberSplit2 = 1, 0
     if (amount == None):
          return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2]
     elif (amount == 3):
          return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2].split(string3)[numberSplit3]
     
def formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None):
     __reg = attr.ib(0).counter
     _revision = attr.ib()
     __reg += 1 
     dataForm = {}
     
     if (requireGraphql == None):
          dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
          dataForm["jazoest"] = dataFB["jazoest"]
          dataForm["__a"] = 1
          dataForm["__user"] =str(dataFB["FacebookID"])
          dataForm["__req"] = str_base(__reg, 36) 
          dataForm["__rev"] = dataFB["client_revision"]
          dataForm["av"] = dataFB["FacebookID"]
          dataForm["fb_api_caller_class"] = "RelayModern"
          dataForm["fb_api_req_friendly_name"] = FBApiReqFriendlyName
          dataForm["server_timestamps"] = "true"
          dataForm["doc_id"] = str(docID)
     else:
          dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
          dataForm["jazoest"] = dataFB["jazoest"]
          dataForm["__a"] = 1
          dataForm["__user"] =str(dataFB["FacebookID"])
          dataForm["__req"] = str_base(__reg, 36) 
          dataForm["__rev"] = dataFB["client_revision"]
          dataForm["av"] = dataFB["FacebookID"]

     return dataForm
     
def clearHTML(text):
     regex = re.compile(r'<[^>]+>')
     return regex.sub('', text)
     
def mainRequests(urlRequests, dataForm, setCookies):
     return {
          "headers": Headers(setCookies, dataForm),
          "timeout": 5,
          "url": urlRequests, # "https://www.facebook.com/api/graphql/",
          "data": dataForm,
          "cookies": parse_cookie_string(setCookies),
          "verify": True
     }
     
def generate_session_id():

     """Generate a random session ID between 1 and 9007199254740991."""
     return random.randint(1, 2 ** 53)  

def generate_client_id():
     
     def gen(length):
          return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
     return gen(8) + '-' + gen(4) + '-' + gen(4) + '-' + gen(4) + '-' + gen(12)
     
def json_minimal(data):

     """Get JSON data in minimal form."""
     return json.dumps(data, separators=(",", ":"))

def _set_chat_on(value):

     return json_minimal(value)

def gen_threading_id():

     return str(
          int(format(int(time.time() * 1000), "b") + 
          ("0000000000000000000000" + 
          format(int(random.random() * 4294967295), "b"))
          [-22:], 2)
     )

def require_list(list_):
     if isinstance(list_, list):
          return set(list_)
     else:
          return set([list_])
def get_files_from_paths(filenames):
     
     files = [filenames, open(filenames, "rb"), guess_type(filenames)[0]]
     yield files
     