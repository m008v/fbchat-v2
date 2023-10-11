import json, requests, time, json, attr, random, re, string
import datetime 
import __facebookToolsV2
from utils import Headers, digitToChar, str_base, dataSplit, parse_cookie_string, formAll, mainRequests

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
          """Args:
               newContents: new content bio FB (eg. MinhHuyDev) | typeInput: str
               uploadPost: Create an post about this change (eg. True/False) | typeInput: bool
          """
          
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
          """Args:
               newContents: content of post to create (eg. MinhHuy create new post!) | typeInput: str
               attachmentID: Coming soon....
          """
          
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
          """Args:
               statusBusiness: Do you want it on or off? (eg. True/False) | typeInput: bool
          """
          
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
          """Args:
               keywordSearch: Content to search for on FB (eg. Mark Zuckerberg) | typeInput: str
          """
          
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
    
     def createItemMarketplace(self, nameItem, brandItem, priceItem, currencyItem, decriptionItem, hashtagList, typeItem, photoIDList, locationSeller):
          
          # Được lấy dữ liệu và viết vào lúc: 22:25 Thứ 3, ngày 10/10/2023. Tác giả: MinhHuyDev
          # Thank you @syrex1013 (Github) very much for your idea
          
          """Args:
               nameItem: Name of item for sale (eg. Gucci Flora) | typeInput: str
               brandItem: Brand of item for sale (eg. Gucci) | typeInput: str
               priceItem: Price of item for sale (eg. 1050) | typeInput: int
               currencyItem: Currency of item for sale (eg. USD) | typeInput: str
               decriptionItem: Description of item | typeInput: str
               hashtagList: Hashtag of item (eg. ["Gucci", "GucciFlora"]) | typeInput: list
               typeItem: type of item (eg. Tools) | typeItem: str
               photoIDList: image of item (eg. [1, 2, 3]) | typeInput: list
               locationSeller: location of seller/item (eg. {"latitude": 11.5614, "longitude": 108.9935}) typeInput: dict
          """
          #Note: You can upload images & get ID images from plugins: __uploadImages.py
          
          categoryDict = {
               "Home&Garden": {
                    "Tools": 2171028376552553,
                    "Furniture": 1583634935226685,
                    "Household": 1569171756675761,
                    "Garden": 800089866739547,
                    "Appliances": 678754142233400
               }
               # There are more options than that... Please continue to develop it for me ¯⁠\⁠_⁠(⁠ツ⁠)⁠_⁠/⁠¯
          }
          
          dataForm = formAll(self.dataFB, "useCometMarketplaceListingCreateMutation", 5033081016747999)
          dataForm["variables"] = json.dumps(
               {
                    "input": {
                         "client_mutation_id": "3",
                         "actor_id": self.dataFB["FacebookID"],
                         "attribution_id_v2": f"CometMarketplaceComposerRoot.react,comet.marketplace.composer,unexpected,{int(time.time() * 1000)},{self.dataFB['jazoest']},1606854132932955,;CometMarketplaceComposerRoot.react,comet.marketplace.composer,via_cold_start,{int(time.time() * 1000)},{self.dataFB['jazoest']},1606854132932955,",
                         "audience": {
                              "marketplace": {
                                   "marketplace_id":"2171028376552553"
                              }
                         },
                         "data": {
                              "common": {
                                   "attribute_data_json": '{\"vt_attributes_free_form\":{\"372885700169792\":\"' + brandItem + '\"},\"vt_attributes_normalized\":{},\"condition\":\"new\",\"brand\":\"' + brandItem + '\"}',
                                   "category_id": categoryDict["Home&Garden"][typeItem], # id Type of item
                                   "commerce_shipping_carrier": None,
                                   "commerce_shipping_carriers": [],
                                   "comparable_price": "null",
                                   "cost_per_additional_item": None,
                                   "delivery_types":["IN_PERSON"],
                                   "description":{
                                        "text": decriptionItem
                                   },
                                   "draft_type": None,
                                   "hidden_from_friends_visibility": "VISIBLE_TO_EVERYONE",
                                   "is_personalization_required": None,
                                   "is_preview": False,
                                   "item_price":{
                                        "currency": currencyItem, #"VND",
                                        "price": priceItem #"400000"
                                   },
                                   "latitude": locationSeller.get('latitude'),
                                   "longitude": locationSeller.get('longitude'), 
                                   "min_acceptable_checkout_offer_price": "null",
                                   "personalization_info": None,
                                   "product_hashtag_names": hashtagList,
                                   "quantity": -1,
                                   "shipping_calculation_logic_version": None,
                                   "shipping_cost_option": "BUYER_PAID_SHIPPING",
                                   "shipping_cost_range_lower_cost": None,
                                   "shipping_cost_range_upper_cost": None,
                                   "shipping_label_price": "0",
                                   "shipping_label_rate_code": None,
                                   "shipping_label_rate_type": None,
                                   "shipping_offered": False,
                                   "shipping_options_data": [],
                                   "shipping_package_weight": None,
                                   "shipping_price": "null",
                                   "shipping_service_type": None,
                                   "sku": "",
                                   "source_type": "marketplace_unknown",
                                   "suggested_hashtag_names": [],
                                   "surface": "composer",
                                   "title": nameItem,
                                   "variants": [],
                                   "video_ids": [],
                                   "xpost_target_ids": [],
                                   "photo_ids": photoIDList #["10108549460594323"]
                              }
                         }
                    }
               }
          )
          
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          try:
               urlPost = sendRequests['data']['marketplace_listing_create']['listing']['story']['url']
               idPost = sendRequests['data']['marketplace_listing_create']['listing']['story']['id']
               a = {
                    "success": 1, 
                    "messages": "Tạo bài bán hàng thành công!", 
                    "data": {
                         "url": urlPost,
                         "id": idPost
                    }
               }
          except:
               a = {
                    "error": 1,
                    "messages": "Đã xảy ra lỗi, tạo bài bán hàng thất bại: " + str(sendRequests)
               }
          
          return a
          
     def getInformationProductItemMarketPlace(self, idProductItem):
     
          # Được lấy dữ liệu và viết vào lúc: 22:25 Thứ 3, ngày 10/10/2023. Tác giả: MinhHuyDev
          # Thank you @syrex1013 (Github) very much for your idea

     
          """Args:
               idProductItem: ID of item (eg. 1176770623712137) | typeInput: str
          """
          
          #Note: How to get ID of item? It's right on the product link: https://www.facebook.com/marketplace/item/1176770623712137/ | ID item: 1176770623712137
          
          dataForm = formAll(self.dataFB, "MarketplacePDPContainerQuery", 6720440741405337)
          dataForm["variables"] = json.dumps(
               {
                    "UFI2CommentsProvider_commentsKey": "MarketplacePDP",
                    "feedbackSource": 56,
                    "feedLocation": "MARKETPLACE_MEGAMALL",
                    "referralCode": "marketplace_top_picks",
                    "scale": 3,
                    "should_show_new_pdp": False,
                    "targetId": idProductItem,
                    "useDefaultActor": False,
                    "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False
               }
          )
     
          sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, self.dataFB["cookieFacebook"])).text)
          
          try:
               mainData = sendRequests['data']['viewer']['marketplace_product_details_page']
               a = {
                    "success": 1,
                    "messages": "Lấy thông tin sản phẩm thành công!",
                    "data": {
                         "productName": mainData['marketplace_listing_renderable_target']['marketplace_listing_title'],
                         "locationSeller": mainData['marketplace_listing_renderable_target']['location'],
                         "productDescription": mainData['target']['redacted_description']['text'],
                         "productPrice": {
                              "price": mainData['target']['listing_price']['amount'],
                              "currency": mainData['target']['listing_price']['currency']
                         },
                         "nameSeller": mainData['target']['story']['actors'][0]['name'],
                         "idSeller": mainData['target']['story']['actors'][0]['id'],
                         "urlProduct": mainData['target']['story']['url'],
                         "createdAt": str(datetime.datetime.fromtimestamp(mainData['target']['creation_time']))
                    }
               }
          except:
               a = {
                    "error": 1,
                    "messages": "Đã xảy ra lỗi, lấy thông tin bài viết thất bại bại: " + str(sendRequests)
               }
               
          return a
               
#Author: MinhHuyDev (Nguyen Minh Huy)