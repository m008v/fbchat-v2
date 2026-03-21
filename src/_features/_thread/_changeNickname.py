import json, requests
from _core._utils import formAll, mainRequests, formatResults

def func(datatFB, threadID, idUser, NewNickname): # Thay đổi biệt danh người dùng
     
    dataForm = formAll(datatFB, requireGraphql=False)
    dataForm["nickname"] = NewNickname
    dataForm["participant_id"] = idUser
    dataForm["thread_or_other_fbid"] = str(threadID)

    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/save_thread_nickname/?source=thread_settings&dpr=1", dataForm, datatFB["cookieFacebook"])).text.split("for (;;);")[1])
    
    
    if sendRequests.get("error"):
        match sendRequests.get("error"):
            case 1545014:
                return formatResults("error", "Người dùng không tồn tại trong nhóm/cuộc trò chuyện.")
            case 1357031:
                return formatResults("error", "Người dùng không tồn tại.")
            case _:
                return formatResults("error", "Lỗi không xác định.")
    else:
        return formatResults("success", "Thay đổi biệt danh người dùng thành công.")