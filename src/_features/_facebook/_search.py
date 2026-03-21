import requests, json, random
from _core._utils import formAll, mainRequests, randStr

def func(dataFB, keywordSearch): # Tìm kiếm trên Facebook
    
    # Được lấy dữ liệu và viết vào lúc: 01:42 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
    """Args:
        keywordSearch: Content to search for on FB (eg. Mark Zuckerberg) | typeInput: str
    """
    
    dataForm = formAll(dataFB, "SearchCometResultsInitialResultsQuery", 6866854183333610)
    dataForm["variables"] = json.dumps(
        {
            "count": 5,
            "allow_streaming": False,
            "args": {
                    "callsite": "COMET_GLOBAL_SEARCH",
                    "config": {
                        "exact_match": False,
                        "high_confidence_config": None,
                        "intercept_config": None,
                        "sts_disambiguation": None,
                        "watch_config":None
                    },
                    "context": {
                        "bsid": str(randStr(8) + "-" + randStr(4) + "-" + randStr(4) + "-" + randStr(4) + "-" + randStr(12)),
                        "tsid": str(random.random())
                    },
                    "experience": {
                        "encoded_server_defined_params": None,
                        "fbid": None,
                        "type": "GLOBAL_SEARCH"
                    },
                    "filters": [],
                    "text": str(keywordSearch)
            },
            "cursor": None,
            "feedbackSource": 23,
            "fetch_filters": True,
            "renderLocation": "search_results_page",
            "scale": 3,
            "stream_initial_count": 0,
            "useDefaultActor": False,
            "__relay_internal__pv__SearchCometResultsShowUserAvailabilityrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False,
            "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
            "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
            "__relay_internal__pv__StoriesRingrelayprovider": False
        }
    )
    
    listResultSearch = []
    dictListResultSearch = []
    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
    try:
        getDataResultSearch = sendRequests["data"]["serpResponse"]["results"]["edges"][0]["relay_rendering_strategy"]["result_rendering_strategies"]
        for dataResults in getDataResultSearch:
            dictListResultSearch.append({
                "name": dataResults["view_model"]["profile"]["name"],
                "id": dataResults["view_model"]["profile"]["id"],
                "url": dataResults["view_model"]["profile"]["url"]
            })
            listResultSearch.append("🔮Tên người dùng: " + dataResults["view_model"]["profile"]["name"] + "\n⚗️ID người dùng: " + dataResults["view_model"]["profile"]["id"] + "\n🏷️Liên kết trang cá nhân: " + dataResults["view_model"]["profile"]["url"] + "\n≈ ≈ ≈ ≈ ≈ ≈ ≈ ≈")
        return {
            "success": 1,
            "searchResults": "≈ ≈ ≈ Tìm Kiếm Facebook ≈ ≈ ≈\n\n" + "\n".join(listResultSearch) + "\n🔎Từ khoá tìm kiếm: " + str(keywordSearch) + "\n📊Số lượng kết quả: 5",
            "searchResultsDict": dictListResultSearch
        }
    except Exception as errLog:
        return {
            "error": 1,
            "messages": "ERR: " + str(errLog)
        }