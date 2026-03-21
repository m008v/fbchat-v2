import requests, json, random
from _core._utils import formAll, mainRequests

def func(dataFB, newContents, uploadPost=False): # Thay đổi Bio trên trang Facebook
    
    # Được lấy dữ liệu và viết vào lúc: 09:10 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
    """Args:
        newContents: new content bio FB (eg. MinhHuyDev) | typeInput: str
        uploadPost: Create an post about this change (eg. True/False) | typeInput: bool
    """
    
    dataForm = formAll(dataFB, "ProfileCometSetBioMutation", 6293552847364844)
    dataForm["variables"] = json.dumps(
        {
            "input": {
                    "bio": str(newContents),
                    "publish_bio_feed_story": uploadPost,
                    "actor_id": dataFB["FacebookID"],
                    "client_mutation_id": str(round(random.random() * 1024))
            },
            "hasProfileTileViewID": False,
            "profileTileViewID": None,
            "scale": 1
        }
    )
    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
    
    if (sendRequests.get("data")):
        checkResultsChangeBio = sendRequests.get("data").get("profile_intro_card_set").get("profile_intro_card").get("bio")
        if (checkResultsChangeBio.get("text") == newContents):
            return {
                    "success": 1,
                    "messages": "Thay đổi bio của bạn thành công!!"
            }
        else:
            return {
                    "error": 1,
                    "description": "??"
            }
    else:
        return {
            "error": 1
        }
        