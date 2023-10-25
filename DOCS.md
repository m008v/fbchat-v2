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
user = "Booking.MinhHuyDev"
passw = "123abcxyz@"
twofa = None
clientLogin = __facebookLoginV2.loginFB(user, passw, twofa)
resultLogin = clientLogin.main()
print(resultLogin)
```
