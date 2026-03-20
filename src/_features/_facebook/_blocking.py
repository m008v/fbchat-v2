import requests, json, random
from _core._utils import formAll, mainRequests  

def func(dataFB, idUser, choiceInteract): # Tương tác Chặn và bỏ chặn người dùng

    # Được lấy dữ liệu và viết vào lúc: 03:12 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
    """Args:
        idUser: ID of the user to block/unblock (eg. 4) | typeInput: str/int
        choiceInteract: Do you want to block or unblock? (eg. block/unblock) | typeInput: str
    """

    if (choiceInteract == "block"):
        
        friendlyName = "ProfileCometActionBlockUserMutation"
        docID = "6305880099497989"
        variables = json.dumps(
            {
                    "collectionID": None,
                    "hasCollectionAndSectionID": False,
                    "input": {
                        "blocksource": "PROFILE",
                        "should_apply_to_later_created_profiles": False,
                        "user_id": int(idUser),
                        "actor_id": dataFB["FacebookID"],
                        "client_mutation_id": str(round(random.random() * 1024))
                    },
                    "scale": 3,
                    "sectionID": None,
                    "isPrivacyCheckupContext": False
            }
        )
    
    elif (choiceInteract == "unblock"):
    
        friendlyName = "BlockingSettingsBlockMutation"
        docID = "6009824239038988"
        variables = json.dumps(
            {
                    "input": {
                        "block_action": "UNBLOCK",
                        "setting": "USER",
                        "target_id": idUser, 
                        "actor_id": dataFB["FacebookID"],
                        "client_mutation_id": "1"
                    },
                    "profile_picture_size": 36
            }
        )
        
    else:
    
        return {
            "error": 1,
            "messages": "Không tồn tại lệnh này."
        }
    
    dataForm = formAll(dataFB, friendlyName, docID)
    dataForm["variables"] = variables
    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
    
    if (choiceInteract == "block"):
        
        if (sendRequests.get("data")):
            return {
                    "success": 1,
                    "messages": "Chặn người dùng thành công!"
            }
        else:
            return {
                    "error": 1,
                    "messages": "Chặn người dùng thất bại!"
            }
    
    elif (choiceInteract == "unblock"):
        
        if (sendRequests.get("data")):
            return {
                    "success": 1,
                    "messages": "Bỏ chặn người dùng thành công!"
            }
        else:
            return {
                    "error": 1,
                    "messages": "Bỏ chặn người dùng thất bại!"
            } 