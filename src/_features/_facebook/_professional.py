import requests, json, random
from _core._utils import formAll, mainRequests

def func(dataFB, statusBusiness=None): # Bật chế độ chuyên nghiệp Trang cá nhân
          
    # Được lấy dữ liệu và viết vào lúc: 01:03 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
    """Args:
        statusBusiness: Do you want it on or off? (eg. True/False) | typeInput: bool
    """
    
    if ((statusBusiness.lower() == "on") | (statusBusiness.lower() == "bật") | (statusBusiness == True)):
        docID = "6580386111988379"
        friendlyName = "CometProfilePlusOnboardingDialogTransitionMutation"
        variables = json.dumps(
            {
                    "category_id": int(random.random() * 1738263827237839),
                    "surface": None
            }
        )
    elif ((statusBusiness.lower() == "off") | (statusBusiness.lower() == "tắt") | (statusBusiness == False)):
        docID = "4947853815250139"
        friendlyName = "CometProfilePlusRollbackMutation"
        variables = json.dumps({})
    else:
        return {
            "error": -1,
            "messages": "Không có sự lựa chọn được đưa ra."
        }
    
    dataForm = formAll(dataFB, friendlyName, docID)
    dataForm["variables"] = variables
        
    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
        
    if (sendRequests.get("data")):
        return {
            "success": 1,
            "messages": "Bật trang cá nhân chuyên nghiệp thành công!" if ((statusBusiness.lower() == "on") | (statusBusiness.lower() == "bật")) else "Tắt trang cá nhân chuyên nghiệp thành công!",
        }
    else:
        return {
            "error": 1,
            "message": sendRequests["errors"][0]["message"]
        }