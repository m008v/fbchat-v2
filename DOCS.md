# Documentation & Question

* [`How to login?`](#loginFB)
  
---------------------------------------

<a name="loginFB"></a>
### How to login?

#### 1.Login with Account

**Notes:** You can access this library by logging in with your account/password and two-factor authentication code (if available) Facebook. However, we encourage users to use the Facebook Cookie instead of logging in with account/password.

*🦖*In the `src` of **fbchat-v2**, there is a file named *__facebookLoginV2.py*. Call it and fill in the arguments it requires (details below).

**__Arguments__**:

* `username`: Numberphone/gmail or ID user.
* `password`: Password for Account.
* `2fa`: Two-factor authentication code (if available)

Below is the sample code:

```python
import __facebookLoginV2
#or import src.__facebookLoginV2 if you place the calling file outside of src
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
else:
     setCookies = resultLogin['success']['setCookies']
     print("Login successful IDFB: {setCookies.split('c_user=')[1].split(';')[0]}")
     print("My cookie account: {setCookies}")
```
⚠️***WARNING***: **Facebook's Cookie & AccessToken** are very *crucial*. Malicious actors can peek at them on your screen when displayed, or even hackers attacking your computer (*botnet*) might steal them, and the risk to your Facebook account is very high! You can learn more about this [here](https://www.facebook.com/privacy/policies/cookies/?_rdr).
