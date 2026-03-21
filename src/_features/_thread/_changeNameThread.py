import json, requests, time, random
from unittest import case
from _core._utils import formAll, mainRequests, formatResults

def func(dataFB, threadID, newNameThread): # Thay đổi tên nhóm
          
    randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))

    dataForm = formAll(dataFB, requireGraphql=False)
    dataForm["client"] = "mercury"
    dataForm["action_type"] = "ma-type:log-message"
    dataForm["thread_id"] = ""
    dataForm["author_email"] = ""
    dataForm["action_type"] = ""
    dataForm["timestamp"] = int(time.time() * 1000)
    dataForm["timestamp_absolute"] = "Today"
    dataForm["author"] = "fbid:" + str(dataFB["FacebookID"])
    dataForm["is_unread"] = False
    dataForm["is_cleared"] = False
    dataForm["is_forward"] = False
    dataForm["is_filtered_content"] = False
    dataForm["is_filtered_content_bh"] = False
    dataForm["is_filtered_content_account"] = False
    dataForm["is_filtered_content_quasar"] = False
    dataForm["is_filtered_content_invalid_app"] = False
    dataForm["is_spoof_warning"] = False
    dataForm["thread_fbid"] = str(threadID)
    dataForm["thread_name"] = newNameThread
    dataForm["thread_id"] = str(threadID)
    dataForm["source"] = "source:chat:web"
    dataForm["source_tags[0]"] = "source:chat"
    dataForm["client_thread_id"] = "root:" + randomNumber
    dataForm["offline_threading_id"] = randomNumber
    dataForm["message_id"] = randomNumber
    dataForm["threading_id"] = "<{}:{}-{}@mail.projektitan.com>".format(int(time.time() * 1000), int(random.random() * 4294967295), hex(int(random.random() * 2 ** 31))[2:])
    dataForm["ephemeral_ttl_mode"] = "0"
    dataForm["manual_retry_cnt"] = "0"
    dataForm["ui_push_phase"] = "V3"
    dataForm["log_message_type"] = "log:thread-name"
    # dataForm["thread_name"] = newNameThread
    # dataForm["thread_id"] = self.threadID


    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/set_thread_name/", dataForm, dataFB["cookieFacebook"])).text.split("for (;;);")[1])

    if (sendRequests.get("error")):
        match sendRequests.get("error"):
            case 1545012:
                return formatResults("error", "Bạn không thể thay đổi tên nhóm khi bạn không phải là một thành viên của nhóm.")
            case 1545003:
                return formatResults("error", "Không thể thay đổi tên nhóm không tồn tại.")
    else:
        return formatResults("error", "Thay đổi tên nhóm thành công.")