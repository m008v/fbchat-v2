import json, requests, time, json, attr, random, re, string
import datetime 
import __facebookToolsV2
from utils import Headers, digitToChar, str_base, dataSplit, parse_cookie_string, formAll, mainRequests
# from LorenBot.plugins.utils import Headers, digitToChar, str_base, dataSplit, parse_cookie_string, formAll, mainRequests
# from LorenBot.plugins import __facebookToolsV2

def randStr(length):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def clearHTML(text):
     regex = re.compile(r'<[^>]+>')
     return regex.sub('', text)

class facebookTools:

     def __init__(self, dataFB):
          self.dataFB = dataFB # Get from __facebookToolsV2.dataGetHome("<cookie tài khoản Facebook>")

     def changeBioFacebook(self, newContents, uploadPost): # Thay đổi Bio trên trang Facebook
          
          # Được lấy dữ liệu và viết vào lúc: 09:10 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
          
          dataForm = formAll(self.dataFB, "ProfileCometSetBioMutation", 6293552847364844)
          dataForm["variables"] = json.dumps(
               {
                    "input": {
                         "bio": str(newContents),
                         "publish_bio_feed_story": uploadPost,
                         "actor_id": self.dataFB["FacebookID"],
                         "client_mutation_id": str(round(random.random() * 1024))
                    },
                    "hasProfileTileViewID": False,
                    "profileTileViewID": None,
                    "scale": 1
               }
          )
          
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
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
               
               
     def createPostFacebook(self, newContents, attachmentID=None): # Tạo bài viết trên Facebook
          
          # Được lấy dữ liệu và viết vào lúc: 09:40 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
          
          dataForm = formAll(self.dataFB, "ComposerStoryCreateMutation", 6534257523262244)
          dataForm["variables"] = json.dumps(
               {
                    "input": {
                         "composer_entry_point": "inline_composer",
                         "composer_source_surface": "timeline",
                         "source": "WWW",
                         "attachments": [],
                         "audience": {
                              "privacy": {
                                   "allow": [],
                                   "base_state": "EVERYONE",
                                   "deny": [],
                                   "tag_expansion_state": "UNSPECIFIED"
                              }
                         },
                         "message": {
                              "ranges": [],
                              "text": newContents
                         },
                         "with_tags_ids": [],
                         "inline_activities": [],
                         "explicit_place_id": "0",
                         "text_format_preset_id": "0",
                         "logging": {
                              "composer_session_id": self.dataFB["sessionID"]
                         },
                         "navigation_data": {
                              "attribution_id_v2": f"ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,tap_bookmark,{int(time.time() * 1000)},{self.dataFB['jazoest']},{self.dataFB['FacebookID']}"
                         },
                         "tracking": "[null]",
                         "actor_id": self.dataFB["FacebookID"],
                         "client_mutation_id": "1"
                    },
                    "displayCommentsFeedbackContext": None,
                    "displayCommentsContextEnableComment": None,
                    "displayCommentsContextIsAdPreview": None,
                    "displayCommentsContextIsAggregatedShare": None,
                    "displayCommentsContextIsStorySet": None,
                    "feedLocation":"TIMELINE",
                    "focusCommentID": None,
                    "scale": str(round(random.random() * 1024)),
                    "privacySelectorRenderLocation":"COMET_STREAM",
                    "renderLocation":"timeline",
                    "useDefaultActor": False,
                    "inviteShortLinkKey": None,
                    "isFeed": False,
                    "isFundraiser": False,
                    "isFunFactPost": False,
                    "isGroup": False,
                    "isEvent": False,
                    "isTimeline": True,
                    "isSocialLearning":False,
                    "isPageNewsFeed": False,
                    "isProfileReviews": False,
                    "isWorkSharedDraft": False,
                    "UFI2CommentsProvider_commentsKey":"ProfileCometTimelineRoute",
                    "hashtag": None,
                    "canUserManageOffers": False,
                    "__relay_internal__pv__IsWorkUserrelayprovider": False,
                    "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                    "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
                    "__relay_internal__pv__StoriesRingrelayprovider":False
               }
          )
                         
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          if (sendRequests.get("data")):
               return {
                    "success": 1,
                    "messages": "Tạo bài viết thành công!",
                    "urlPost": sendRequests["data"]["story_create"]["story"]["url"]
               }
          else:
               return {
                    "error": 1,
                    "messages": sendRequests["errors"][0]["message"]
               }
          
     def getMessageRequests(self): # Lấy danh sách tin nhắn chờ
          
          # Được lấy dữ liệu và viết vào lúc: 21:43 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
          # Lưu Ý: Này chỉ lấy từ m.facebook.com nên giới hạn (limit) tin nhắn là 5 thôi :v
          
          sendRequests = requests.get(**mainRequests("https://m.facebook.com/messages/?folder=pending", None, self.dataFB["cookieFacebook"])).text
          listMessage = []
          try:
               lengthMessageRequests = sendRequests.count("<a href=\"/messages/read/") 
               if (lengthMessageRequests == 0):
                    return {
                         "notfound": 1,
                         "message": "Không tìm thấy dữ liệu này về tin nhắn chờ."
                    }
               else:
                    for messageAmountAdded in range(2, lengthMessageRequests):
                         try:
                              getAllDataMessage = dataSplit("<a href=\"/messages/read/", "<a href=\"", messageAmountAdded, 0, sendRequests)
                              idUser = clearHTML(dataSplit("%3A", "&", 1, 0, str(re.search(f"tid=cid.c.{dataFB['FacebookID']}%3A(.*?)&amp;", getAllDataMessage))))
                              nameUser = clearHTML(dataSplit("\">", "</a></h3><h3", 1, 0, getAllDataMessage))
                              textContents = dataSplit("\">", "</span></h3><h3><span", 3, 0, getAllDataMessage)
                              DateTimeSendMessage = clearHTML(dataSplit("<abbr>", "</", 1, 0, getAllDataMessage))
                              try: contentMessage = textContents.split("</span></h3><h3")[0]
                              except: contentMessage = clearHTML(textContents)
                              listMessage.append(f"≈ ≈ ≈ ≈ ≈ ≈\n🏷️Tên người dùng: {nameUser}\n🪂ID người dùng: {idUser}\n🖨️Nội dung tin nhắn: {contentMessage}\n🗓️Thời gian gửi: {DateTimeSendMessage}")
                         except:
                              pass
                    
                    return {
                         "success": 1,
                         "messageRequests": "\n".join(listMessage)
                    }
          except Exception as errLog:
               return {
                    "error": 1,
                    "message": "ERR: " + str(errLog)
               }
          
     def onBusinessOnFacebookProfile(self, statusBusiness=None): # Bật chế độ chuyên nghiệp Trang cá nhân
          
          # Được lấy dữ liệu và viết vào lúc: 01:03 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
          
          if ((statusBusiness.lower() == "on") | (statusBusiness.lower() == "bật")):
               docID = "6580386111988379"
               friendlyName = "CometProfilePlusOnboardingDialogTransitionMutation"
               variables = json.dumps(
                    {
                         "category_id": int(random.random() * 1738263827237839),
                         "surface": None
                    }
               )
          elif ((statusBusiness.lower() == "off") | (statusBusiness.lower() == "tắt")):
               docID = "4947853815250139"
               friendlyName = "CometProfilePlusRollbackMutation"
               variables = json.dumps({})
          else:
               return {
                    "error": -1,
                    "messages": "Không có sự lựa chọn được đưa ra."
               }
          
          dataForm = formAll(self.dataFB, friendlyName, docID)
          dataForm["variables"] = variables
               
          
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
               
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
          
               
     # def registerAccountProfileOnProfile(self, newName, newUsername): # Tạo một trang cá nhân khác trên chinh tài khoản Facebook
     
          # # Được lấy dữ liệu và viết vào lúc: 01:14 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
     
          # dataForm = formAll(dataFB, "AdditionalProfileCreateMutation", 4699419010168408)
          # dataForm["variables"] = json.dumps(
               # {
                    # "input": {
                         # "name": newName,
                         # "source": "PROFILE_SWITCHER",
                         # "user_name": newUsername,
                         # "actor_id": dataFB["FacebookID"],
                         # "client_mutation_id": str(round(random.random() * 1024))
                    # }
               # }
          # )
          
          # mainRequests = {
               # "headers": Headers(dataFB["cookieFacebook"], dataForm),
               # "timeout": 60000,
               # "url": "https://www.facebook.com/api/graphql/",
               # "data": dataForm,
               # "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
               # "verify": True
          # }
         
          # sendRequests = json.loads(requests.post(**mainRequests).text)
          
          # if (sendRequests.get("data")):
               # if (sendRequests.get("data").get("additional_profile_create").get("error_message")):
                    # return {
                         # "error": 1,
                         # "message": sendRequests["data"]["additional_profile_create"]["error_message"]
                    # }
               # else:
                    # return {
                         # "success": 1,
                         # "messages": "Tạo trang cá nhân khác trên tài khoản Facebook thành công!"
                    # }
          # else:
               # return {
                    # "error": 1,
                    # "messages": sendRequests["errors"][0]["message"]
               # }
     
     def searchInFacebook(self, keywordSearch): # Tìm kiếm trên Facebook
          
          # Được lấy dữ liệu và viết vào lúc: 01:42 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
          
          dataForm = formAll(self.dataFB, "SearchCometResultsInitialResultsQuery", 6866854183333610)
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
         
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          try:
               getDataResultSearch = sendRequests["data"]["serpResponse"]["results"]["edges"][0]["relay_rendering_strategy"]["result_rendering_strategies"]
               for dataResults in getDataResultSearch:
                    listResultSearch.append("🔮Tên người dùng: " + dataResults["view_model"]["profile"]["name"] + "\n⚗️ID người dùng: " + dataResults["view_model"]["profile"]["id"] + "\n🏷️Liên kết trang cá nhân: " + dataResults["view_model"]["profile"]["profile_url"] + "\n≈ ≈ ≈ ≈ ≈ ≈ ≈ ≈")
               return {
                    "success": 1,
                    "searchResults": "≈ ≈ ≈ Tìm Kiếm Facebook ≈ ≈ ≈\n\n" + "\n".join(listResultSearch) + "\n🔎Từ khoá tìm kiếm: " + str(keywordSearch) + "\n📊Số lượng kết quả: 5"
               }
          except Exception as errLog:
               return {
                    "error": 1,
                    "messages": "ERR: " + str(errLog)
               }
               
     def getNotificationRecentlyFacebook(self): # Lấy thông báo Facebook
          
          # Được lấy dữ liệu và viết vào lúc: 02:32 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
          
          dataForm = formAll(self.dataFB, "CometNotificationsDropdownQuery", 6770067089747450)
          dataForm["variables"] = json.dumps(
               {
                    "count":15,
                    "environment":"MAIN_SURFACE",
                    "scale":3
               }
          )
          
          listNotificationResults = []
         
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          try:
               getDataResultNotificationFacebook = sendRequests["data"]["viewer"]["notifications_page"]["edges"]
               for dataResults, sttCount in zip(getDataResultNotificationFacebook, range(1, len(getDataResultNotificationFacebook) + 1)):
                    try:
                         listNotificationResults.append(str(sttCount) + "." + dataResults["node"]["notif"]["body"]["text"])
                    except:
                         pass
          except Exception as errLog:
               return {
                    "error": 1,
                    "messages": "ERR: " + str(errLog)
               }
          return {
               "success": 1,
               "NotificationResults": "≈ ≈ ≈ Thông báo Facebook ≈ ≈ ≈\n\n" + "\n".join(listNotificationResults)
          }
          
     def InteractBlockedAndUnBlocked(self, idUser, choiceInteract): # Tương tác Chặn và bỏ chặn người dùng
     
          # Được lấy dữ liệu và viết vào lúc: 03:12 Thứ 5, ngày 06/07/2023. Tác giả: MinhHuyDev
     
     
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
                              "actor_id": self.dataFB["FacebookID"],
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
                              "actor_id": self.dataFB["FacebookID"],
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
          
          dataForm = formAll(self.dataFB, friendlyName, docID)
          dataForm["variables"] = variables
         
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          if (choiceInteract == "block"):
               
               if (sendRequests.get("data")):
                    return {
                         "success": 1,
                         "messages": "Chặn người dùng thành công!"
                    }
               else:
                    return {
                         "error": 1,
                         "messages": "Chặn người dùng thất bại!!!!!!"
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
                         "messages": "Bỏ chặn người dùng thất bại!!!!!!"
                    } 
    
#Author: MinhHuyDev (Nguyen Minh Huy)
