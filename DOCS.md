# Documentation & Question

* [`Set up import all module`](#SetupModule)
* [`How to login?`](#loginFB)
* [`How to check Live/Die cookie?`](#checkCookie)
* [`How to receive message from Thread/User`](#receiveMessages)
* [`How to send message and unsend one`](#sendMessageAndUnsend)
* [`How to upload attachment files and send them`](#uploadAttachmentAndSend)
---------------------------------------

<a name="SetupModule"></a>
### Set up import all module

Please create a file and *install all the modules* present in here (main.py, mainBot.py, ...). **Example code:**

```python
import __facebookLoginV2, __facebookToolsV2, __messageListenV2, __sendMessage, __unsendMessage
```

**🌟NOTE**: Please create a file inside `fbchat-v2/src` :DD

**YOU MIGHT NOT KNOW**: If you want to create files and **run them outside the fbchat-v2 directory**, you can follow the code snippet below:

```python
from fbchat_v2.src import (args...[...])
```

**First**, please rename the directory name **fbchat-v2**. Replace them from ``fbchat-v2`` *to* ``fbchat_v2`` before executing the above code.

**Secondly**, You *must* change all import modules in the files of the plugins under ``fbchat-v2/src``. Specifically, in the plugins files, there exists a code snippet:

```python
from utils import args...[..]
```

You need to change them from the above to the following:

```python
from fbchat_v2.src.utils import args...[..]
```

**Here** is a specific *example* of the changes:

```python
from utils import digitToChar, Headers, str_base, parse_cookie_string, dataSplit, formAll, mainRequests
```
**change to:**
```python
from fbchat_v2.src.utils import digitToChar, Headers, str_base, parse_cookie_string, dataSplit, formAll, mainRequests
```

<a name="loginFB"></a>
### How to login?

⚠️***WARNING***: **Facebook's Cookie & AccessToken** are very *crucial*. Malicious actors can peek at them on your screen when displayed, or even hackers attacking your computer (*botnet*) might steal them, and the risk to your Facebook account is very high! You can learn more about this [here](https://www.facebook.com/privacy/policies/cookies/?_rdr).

#### 1.Login with Account

**Notes:** You can access this library by logging in with your account/password and two-factor authentication code (if available) Facebook. However, we encourage users to use the Facebook Cookie instead of logging in with account/password.

*🦖*In the `src` of **fbchat-v2**, there is a file named *__facebookLoginV2.py*. Call it and fill in the arguments it requires (details below).

**__Arguments__**:

* `username`: Numberphone/gmail or ID user.
* `password`: Password for Account.
* `2fa`: Two-factor authentication code (if available)

Below is the sample code:

```python
user = "minhhuydev@icloud.com"
passw = "30102007"
twofa = None
clientLogin = __facebookLoginV2.loginFB(user, passw, twofa)
resultLogin = clientLogin.main()
print(resultLogin)
```

When running the above code, it will produce two outcomes (Success or Failure). Below is the `dict` when the login is **successful**:
```python
{'success': {'setCookies': 'c_user=61551671683861; xs=8:51DRVMpDOiHp1A:2:1698481000:-1:8465; fr=0KEtD6nFFrfDEKrJV.AWUAsJnjqK5VxFhFxfHxW8yzaeQ.BlPMNo..AAA.0.0.BlPMNo.AWUl1XTH5G8; datr=aMM8Zb2qBmtztvpdwwrykC6-; ', 'accessTokenFB': 'EAAAAUaZA8jlABO5DKmmquwPkzDdxUcwJ6CKPOqFh0gZBGl8HRhp1o9KhjRsVdXZCMA40JGPLuLxAYsDG6uIKJBPFGfl2iILzknxFfNidfLjICpikgDU2pFzQ4swhb0QUBtVACu3eGH61kBuRr0zQBytGbj9SzmnrK0mujr6wjSZBbCtfgdpwcRwPi8no6Dqb0gZDZD', 'cookiesKey-ValueList': [{'name': 'c_user', 'value': '61551671683861', 'expires': 'Sun, 27 Oct 2024 08:16:40 GMT', 'expires_timestamp': 1730017000, 'domain': '.facebook.com', 'path': '/', 'secure': True, 'samesite': 'None'}, {'name': 'xs', 'value': '8:51DRVMpDOiHp1A:2:1698481000:-1:8465', 'expires': 'Sun, 27 Oct 2024 08:16:40 GMT', 'expires_timestamp': 1730017000, 'domain': '.facebook.com', 'path': '/', 'secure': True, 'httponly': True, 'samesite': 'None'}, {'name': 'fr', 'value': '0KEtD6nFFrfDEKrJV.AWUAsJnjqK5VxFhFxfHxW8yzaeQ.BlPMNo..AAA.0.0.BlPMNo.AWUl1XTH5G8', 'expires': 'Fri, 26 Jan 2024 08:16:40 GMT', 'expires_timestamp': 1706257000, 'domain': '.facebook.com', 'path': '/', 'secure': True, 'httponly': True, 'samesite': 'None'}, {'name': 'datr', 'value': 'aMM8Zb2qBmtztvpdwwrykC6-', 'expires': 'Sun, 01 Dec 2024 08:16:40 GMT', 'expires_timestamp': 1733041000, 'domain': '.facebook.com', 'path': '/', 'secure': True, 'httponly': True, 'samesite': 'None'}]}}
```
Or if the login fails, it will return the following result:
```python
{'error': {'title': 'Wrong Credentials', 'description': 'Invalid username or password', 'error_subcode': 1348131, 'error_code': 401, 'fbtrace_id': 'AQ1wRUfc-SJoGJ4m4iXGy1B'}}
```
If the login is successful, please call the `success` key and go to `setCookies` to retrieve the Cookie and use it for various features of **fbchat-v2**.

If error, you can view the login error details through the `error` key and call `description`. Below is the **example code**:
```python
if resultLogin.get('success') is None:
     raise SystemExit(f"Error login: {resultLogin['error']['description']} | Error code: {resultLogin['error']['error_code']}")
setCookies = resultLogin['success']['setCookies']
print("Login successful IDFB: {setCookies.split('c_user=')[1].split(';')[0]}")
print("My cookie account: {setCookies}")
```

#### 2.Login with CookieFacebook

This is extremely simple, you just need to *pre-login with your Facebook account* in any browser (Chrome, Firefox, ...). Next, press `F12` to open **DevTools**, and `F5` to refresh the page. A series of Facebook requests will appear, you just need to select any request => Choose the `headers` section of that request. Scroll to find the **Cookie**, then copy them and create them as a variable in **your code**:
```python
setCookies = "c_user=61551671683861; xs=8:51DRVMpDOm...[...]"
```

<a name="checkCookie"></a>
### How to check Live/Die cookie?

This is very simple. Facebook always has data (**fb_dtsg**, **jazoest**, ...) sent to *graphql*. If you can obtain. obtain this data => Your Cookie is *working*, and versa vice. Below is the **example code**:
```python
dataFB = __facebookToolsV2.dataGetHome(setCookies)
try:
     print(f"{dataFB['FacebookID']} => Cookies is working!")
except:
     raise SystemExit("Cookies is DIE")
```

<a name="receiveMessages"></a>
### How to receive message from Thread/User?

It seems like a fundamental part is done. Now, let's move on to receiving messages from users and chat groups (thread) on Facebook. First, you need to connect to *Facebook's MQTT through* the module:

**__Arguments__**:

* `fbt`: To retrieve the **last_seq_id** data, we need to *__facebookToolsV2.fbTools()*
* `dataFB`: The Facebook homepage data is retrieved using *__facebookToolsV2.dataGetHome()*

```python
# dataFB: This value has been obtained when checking the LIVE or DIE Cookie. You can find it above
fbt = __facebookToolsV2(dataFB, 0) # default: 0 or None
mainReceiveMsg = __messageListenV2.listeningEvent(fbt, dataFB)
mainReceiveMsg.get_last_seq_id() # Get seq_id
mainReceiveMsg.connect_mqtt() # Start receive message.
```

All received message data will be exported to the *.mqttMessage* file in ``JSON`` format. Below is the successfully received message data:

```json
{
     "body": "b g\u1eedi l\u00e0 n\u00f3 \u0111em \u0111i spam kh\u1eafp group l\u00e0 ch\u1ebft t\u00f4i",
     "timestamp": "1702314310077",
     "userID": "1619995045",
     "messageID": "mid.$gABESRz00DD6SixxBvWMWdb3w_KEg",
     "replyToID": "4805171782880318",
     "type": "thread",
     "attachments": {
          "id": "This is image_url!?",
          "url": "https://scontent.xx.fbcdn.net/v/t1.15752-9/409533780_915397450177903_2930757942430749596_n.png?stp=dst-png_p280x280&_nc_cat=110&ccb=1-7&_nc_sid=8cd0a2&_nc_ohc=3aV5AdDJOsYAX80qeEz&_nc_ad=z-m&_nc_cid=0&_nc_ht=scontent.xx&oh=03_AdSeQesqM3GV7eYtwZrPjsdiqk3j_B9hKqiqEB-NsqBC_g&oe=659E9DE1"
     }
}
```

<a name="sendMessageAndUnsend"></a>
### How to send message and unsend one

To reply or send a message to a thread or user, you need to use the ``__sendMessage.py`` plugin. Below are the arguments and a sample code:

**__Arguments__**:

* `dataFB`: The Facebook homepage data is retrieved using *__facebookToolsV2.dataGetHome()*
* `contentSend`: Content message to send
* `threadID`: ID of **thread/user**
* `typeAttachment`: Type attachment send with message
* `attachmentID`: ID of attachment uploaded.
* `typeChat`: type chat with user/thread
* `replyMessage`:You want to send a message/reply to someone
* `messageID`: ID of message that you need to reply

**YOU SHOULD KNOW**: For the ``replyMessage`` parameter, if you want to *reply* to someone's message, you must include the ``messageID``. If you just want to *send a message* to a thread/user, you can assign any value to replyMessage (other than None)

```python
sendMessageCalled = __sendMessage.api()

# The necessary values - Các giá trị cần thiết
contentSend = "test send!"
threadID = 4805171782880318
typeAttachment = None # Values: gif, image, video, file, audio
attachmentID = None # This value is obtained from __uploadAttachments.py
typeChat = None # "user" = User / Other value = Thread
replyMessage = 1 # None = reply / Other value = only send
messageID = None # messageID value e.g: mid.$gABESRz00DD6SixxBvWMWdb3w_KEg

resultSendMessage = sendMessageCalled.send(dataFB, contentSend, threadID, typeAttachment, attachmentID, typeChat, replyMessage, messageID)
print(resultSentMessage)
```

**NOTE**: Some values already have the default value of **None**, including: ``typeAttachment``, ``attachmentID``, ``typeChat``, ``replyMessage``, and ``messageID``. If you don't want to change their values, please skip them.

Below is the result when the message is sent **successfully**:

```python
{'success': 1, 'payload': {'messageID': 'mid.$cAABa-wot0daSn4Obo2Mbj5L5njhO', 'timestamp': 1702656627619}}
```

But if you want to cancel this message, you can retract it by taking the ``messageID`` from the data sent successfully and calling ``__unsendMessage`` to send a retraction request. Below is a sample code:

```python
messageID = resultSendMessage["payload"]["messageID"]
resultUnsendMessage = __unsendMessage._unsend(messageID, dataFB)
print(resultUnsendMessage)
```

Below is the *successful* unsend result:

```python
{'success': 1, 'messages': 'Thu hồi tin nhắn thành công.'}
```

<a name="uploadAttachmentAndSend"></a>
### How to upload attachment files and send them

Coming soon..?

Lời nhắn của tác giả: Tôi đang khá lười biến để tiếp tục phát triển, nếu bạn muốn làm người đóng góp. Hãy nhắn tin cho tôi😝
Author's note: I'm in a serious relationship with laziness, but if you're feeling adventurous and want to be a contributor, shoot me a message! 😝
22:05 05/01/2024