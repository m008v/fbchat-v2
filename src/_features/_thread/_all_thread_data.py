import requests, random, time, json
from _core._utils import formAll, mainRequests

def func(dataFB): # Lấy dữ liệu những thành phần tin nhắn ở INBOX
     
    randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
    dataForm = formAll(dataFB, requireGraphql=0)
    # dataForm["av"] = dataFB["cookieFacebook"].split("c_user=")[1].split(";")[0]

    dataForm["queries"] = json.dumps({
        "o0": {
            "doc_id": "3336396659757871",
            "query_params": {
                    "limit": 50,
                    "before": None,
                    "tags": ["INBOX"], # INBOX, PENDING, ARCHIVED
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
            }
        }
    })
    
    sendRequests = requests.post(**mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, dataFB["cookieFacebook"]))
    # return sendRequests.text.split("{\"successful_results\"")[0]
    dataGet = sendRequests.text.split('{"successful_results"')[0]
    ProcessingTime = sendRequests.elapsed.total_seconds()
    last_seq_id = json.loads(dataGet)["o0"]["data"]["viewer"]["message_threads"]["sync_sequence_id"]
    try:
        threadIDList = []
        threadNameList = []
        
        getData = json.loads(dataGet)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
        # print(getData)
        for getThreadID in getData:
            if (getThreadID["thread_key"]["thread_fbid"] != None):
                    threadIDList.append(getThreadID["thread_key"]["thread_fbid"])
                    threadNameList.append(getThreadID["name"])
        dataAllThread = {
            "threadIDList": threadIDList,
            "threadNameList": threadNameList,
            "countThread": len(threadIDList)
        }
    except Exception as errLog:
        dataAllThread = {
            "error": str(errLog)
        }
    return {
        "dataGet": dataGet,
        "ProcessingTime": ProcessingTime,
        "last_seq_id": last_seq_id,
        "dataAllThread": dataAllThread
    }

def features(dataGet, threadID, commandUse):
    listData = []
          
    try:
        getData = json.loads(dataGet)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
    except (KeyError, TypeError, json.JSONDecodeError):
        try:
            return json.loads(dataGet)["o0"]["errors"][0]["summary"]
        except (KeyError, TypeError, json.JSONDecodeError):
            return "Không thể xử lý dữ liệu ThreadList."
    for getNeedIDThread in getData:
        if (str(getNeedIDThread["thread_key"]["thread_fbid"]) == str(threadID)):
            dataThread = getNeedIDThread
    
    if (dataThread != None):
        match commandUse:
            case "getAdmin":  # Lấy id Admin Thread
                for dataID in dataThread["thread_admins"]:
                        listData.append(str(dataID["id"]))
                exportData = {
                        "adminThreadList": listData
                }

            case "threadInfomation": # Lấy thông tin Thread
                threadInfoList = dataThread["customization_info"]
                exportData = {
                        "nameThread": dataThread["name"], 
                        "IDThread": threadID, 
                        "emojiThread": threadInfoList["emoji"],
                        "messageCount": dataThread["messages_count"],
                        "adminThreadCount": len(dataThread["thread_admins"]),
                        "memberCount": len(dataThread["all_participants"]["edges"]),
                        "approvalMode": "Bật" if (dataThread["approval_mode"] != 0) else "Tắt",
                        "joinableMode": "Bật" if (dataThread["joinable_mode"]["mode"] != "0") else "Tắt",
                        "urlJoinableThread": dataThread["joinable_mode"]["link"]
                }
            case "exportMemberListToJson": # Chuyển đổi dữ liệu member Thread
                getMemberList = dataThread["all_participants"]["edges"]
                for exportMemberList in getMemberList:
                        dataUserThread = exportMemberList["node"]["messaging_actor"]
                        exportData = json.dumps({
                            dataUserThread["id"]: {
                                "nameFB": str(dataUserThread.get("name")),
                                "idFacebook": str(dataUserThread.get("id")),
                                "profileUrl": str(dataUserThread.get("url")),
                                "avatarUrl": str(dataUserThread["big_image_src"]["uri"]),
                                "gender": str(dataUserThread.get("gender")),
                                "usernameFB": str(dataUserThread.get("username"))
                            }
                        }, skipkeys=True, allow_nan=True, ensure_ascii=False, indent=5)
                        listData.append(exportData)
                exportData = listData
            case _:
                exportData = {
                        "err": "no data"
                }
            
        return exportData
        
    else:
        return "Không lấy được dữ liệu ThreadList, đã xảy ra lỗi T___T"