import requests, json
from _core._utils import formAll, mainRequests, formatResults

def func(dataFB, threadID, newEmoji): # Thay đổi biểu tượng cảm xúc của nhóm
    dataForm = formAll(dataFB, requireGraphql=False)
    dataForm["emoji_choice"] = newEmoji
    dataForm["thread_or_other_fbid"] = threadID

    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/save_thread_emoji/?source=thread_settings&__pc=EXP1%3Amessengerdotcom_pkg", dataForm, dataFB["cookieFacebook"])).text.split("for (;;);")[1])

    if (sendRequests.get("error")):
        error = sendRequests.get("error")
        if error == 1357031:
            return formatResults("error", "Không thể thay đổi trạng thái emoji của một cuộc trò chuyện không tồn tại.")
        else:
            return formatResults("error", "Lỗi không xác định.")
    else:
            return formatResults("success", "Thay đổi biểu tượng cảm xúc nhanh thành công.")