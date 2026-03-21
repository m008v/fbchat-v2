import requests, json, random
from _core._utils import parse_cookie_string, formAll, Headers

def func(dataFB, newName, newUsername): # Tạo một trang cá nhân khác trên chinh tài khoản Facebook
    
    # Được lấy dữ liệu và viết vào lúc: 01:14 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev

    dataForm = formAll(dataFB, "AdditionalProfileCreateMutation", 4699419010168408)
    dataForm["variables"] = json.dumps(
        {
            "input": {
                    "name": newName,
                    "source": "PROFILE_SWITCHER",
                    "user_name": newUsername,
                    "actor_id": dataFB["FacebookID"],
                    "client_mutation_id": str(round(random.random() * 1024))
            }
        }
    )
    
    mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 60000,
        "url": "https://www.facebook.com/api/graphql/",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "verify": True
    }
    
    sendRequests = json.loads(requests.post(**mainRequests).text)
    
    if (sendRequests.get("data")):
        if (sendRequests.get("data").get("additional_profile_create").get("error_message")):
            return {
                    "error": 1,
                    "message": sendRequests["data"]["additional_profile_create"]["error_message"]
            }
        else:
            return {
                    "success": 1,
                    "messages": "Tạo trang cá nhân khác trên tài khoản Facebook thành công!"
            }
    else:
        return {
            "error": 1,
            "messages": sendRequests["errors"][0]["message"]
        }
