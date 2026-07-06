✓Tôn trọng tác giả ❤️
"""

if __name__ == "__main__":
    import os

    # Usage: FBCHAT_USER=xxx FBCHAT_PASS=xxx FBCHAT_2FA=xxx python _facebookLogin.py
    user = os.environ.get("FBCHAT_USER")
    pwd = os.environ.get("FBCHAT_PASS")
    code = os.environ.get("FBCHAT_2FA")
    if not all([user, pwd]):
        print("Thiết lập biến môi trường FBCHAT_USER và FBCHAT_PASS trước khi chạy.")
        raise SystemExit(1)
    result = loginFacebook(user, pwd, code).main()
    print(result)
