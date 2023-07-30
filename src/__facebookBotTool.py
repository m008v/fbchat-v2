import attr, requests, json, re, base64
# from LorenBot.plugins.utils import dataSplit, formAll, parse_cookie_string, digitToChar, str_base
from utils import dataSplit, formAll, parse_cookie_string, digitToChar, str_base, Headers
import __facebookToolsV2

# Author: MinhHuyDev (GitHub)
# Này dành cho mấy bạn sẽ làm Nuôi Facebook =)) nếu biết cách phối hợp

def getAccessTokenFacebook(typeGet, cookieFacebook):
     urlGet = {
          "eaab...": "/docs/FacebookAPI/FacebookAccessToken/Eaabw/?cookie={}",
          "eaav...": "/docs/FacebookAPI/FacebookAccessToken/Eaav/?cookies={}",
     }
     
     ResultAccessToken = requests.get("https://api.mhuyz.dev" + urlGet[typeGet].format(cookieFacebook)).text
     return {
          "data": json.loads(ResultAccessToken),
          "idfb": dataSplit("c_user=", ";", 1, 0, cookieFacebook)
     }
     
     
def getNewFeeds(cookieFacebook):
     listUrl = []
     homeFacebook = requests.get("https://mbasic.facebook.com/home.php", headers={"Cookie": cookieFacebook}).text
     try:
          for totalCount in range(1, len(homeFacebook.split("href=\"/story.php?")) + 1):
               urlPost = str("https://mbasic.facebook.com/story.php?" + dataSplit("href=\"/story.php?", "\"", totalCount, 0, homeFacebook)).replace("&amp;", "&")
               listUrl.append(urlPost)
     except:
          pass
     return listUrl

def reactionPost(setCookie, urlPost, typeReaction):
     requestsRedirect = requests.get(urlPost, headers={"Cookie": setCookie})
     try: idPost = str(requestsRedirect.text.split("top_level_post_id&quot;:&quot;")[1].split(";,")[0]).replace("&quot", "")
     except: idPost = None
     getDataReaction = re.findall('/reactions/picker/?.*?"',requestsRedirect.text)
     DataReaction = requests.get("https://mbasic.facebook.com" + getDataReaction[0].replace('amp;','').replace('"',''),headers={"Cookie": setCookie})
     reactionData = re.findall('/ufi/reaction/?.*?" style', DataReaction.text)
     reactionData = ''.join(reactionData)
     reactionData = reactionData.replace('style', '')
     reactionData = reactionData.split('"')
     if (typeReaction == 'LIKE'): numberSplit = 0
     if (typeReaction == 'LOVE'): numberSplit = 1
     if (typeReaction == 'HAHA'): numberSplit = 3
     if (typeReaction == 'WOW'): numberSplit = 4
     if (typeReaction == 'SAD'): numberSplit = 5
     if (typeReaction == 'ANGRY'): numberSplit = 6
     if (typeReaction == 'THUONGTHUONG'): numberSplit = 2
     sendRequests = requests.get("https://mbasic.facebook.com" + str(reactionData[numberSplit]).replace('amp;','').replace(' ',''), headers={"Cookie": setCookie});
     if "Tham gia Facebook hoặc đăng nhập để tiếp tục." in sendRequests.text:
         resultRequests = {"status": -1, "description": "Cookie Die!!"}
     if "Để bảo vệ cộng đồng khỏi spam" in sendRequests.text:
         resultRequests = {"status": 0, "description": "Facebook Blocked"}
     else:
         resultRequests = {"status": 1, "description": "Reaction sent to Post!", "idPost": idPost}
    
     return resultRequests
def checkCookieLiveDie(cookieFacebook):
      
      ProfileHome = requests.get("https://mbasic.facebook.com/profile.php", headers={"Cookie": cookieFacebook})
      if (ProfileHome.text.find("/login.php") != -1):
          return 0
      else:
          return 1

def getReactionCountPost(feedBackID, dataFB): # Lấy số lượng reaction có trong một bài viết
     
     # The document was written on 28/7/2023 (GMT + 7)
     
     dataForm = formAll(dataFB, "CometUFIReactionsDialogQuery", 6443454529016333)
     dataForm["variables"] = json.dumps(
          {
               "feedbackTargetID": feedBackID,
               "scale": 3
          }
     )
     
     mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 60000,
        "url": "https://www.facebook.com/api/graphql/",
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "data": dataForm,
        "verify": True
     }
     
     sendRequests = json.loads(requests.post(**mainRequests).text)
     
     totalReactionPost = 0 # sendRequests["data"]["node"]["top_reactions"]["count"]
     listUserID = []
     listUserReactionSentToPost = sendRequests["data"]["node"]["important_reactors"]["edges"]
     for dataUser in listUserReactionSentToPost:
          listUserID.append(dataUser["node"]["id"])
          totalReactionPost += 1
     return {
          "data": {
               "totalReactions": totalReactionPost,
               "listUserID": listUserID
          }
     }

def UnfriendFacebook(IDFacebook, dataFB): # Xoá bạn bè trên Facebook
     
     # The document was written on 28/7/2023 (GMT + 7)
     
     dataUnfriend = 'restrictedUserNode' + str(IDFacebook)
     dataForm = formAll(dataFB, "FriendingCometUnfriendMutation", 8752443744796374)
     dataForm["variables"] = json.dumps(
          {
               "input": {
                    "source": "friending_jewel",
                    "unfriended_user_id": str(base64.b64encode(dataUnfriend.encode("utf-8"))).replace("b'", "").replace("'", ""),
                    "actor_id": dataFB["FacebookID"],
                    "client_mutation_id": "1"
               },
               "scale": 3
          }
     )
     
     mainRequests = {
          "headers": Headers(dataFB["cookieFacebook"], dataForm),
          "timeout": 60000,
          "url": "https://www.facebook.com/api/graphql/",
          "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
          "data": dataForm,
          "verify": True
     }
     
     sendRequests = json.loads(requests.post(**mainRequests).text)
     
     return "successful" if (str(sendRequests).find("error") == -1) else "failed"
     
def FriendsWhoHaveNotInteracted(dataFriend, ListFriendSentReactions): # Lọc lại danh sách bạn bè với những người chưa tương tác
     
     totalFriend = dataFriend["totalFriends"]
     friendList = dataFriend["friendList"]
     for friendID, fillerFriendID in zip(friendList, ListFriendSentReactions):
          try:
               friendList.remove(fillerFriendID)
          except:
               pass
     
     return {
          "friendListAfterFillter": friendList,
          "totalFriends": len(friendList)
     }

def getListFriend(accessToken): # Get danh sách bạn bè
     
     mainRequests = {
        "timeout": 60000,
        "url": "https://graph.facebook.com/v11.0/me/friends?access_token={}&limit={}".format(accessToken, 100000),
        "verify": True
     }
     
     sendRequests = json.loads(requests.get(**mainRequests).text)
     
     totalFriendList = len(sendRequests["data"])
     listFriends = []
     for dataID in sendRequests["data"]:
          listFriends.append(dataID["id"])
     return {
          "totalFriends": totalFriendList,
          "friendList": listFriends
     }

def pokeFriendList(userID, dataFB): # Chọc bạn bè
     
     dataForm = formAll(dataFB, "PokesMutatorPokeMutation", 5028133957233114)
     dataForm["variables"] = json.dumps(
          {
               "input": {
                    "client_mutation_id": "1",
                    "actor_id": dataFB["FacebookID"],
                    "user_id": str(userID)
               }
          }
     )
     
     mainRequests = {
          "headers": Headers(dataFB["cookieFacebook"], dataForm),
          "timeout": 60000,
          "url": "https://www.facebook.com/api/graphql/",
          "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
          "data": dataForm,
          "verify": True
     }
     
     sendRequests = json.loads(requests.post(**mainRequests).text)
     
     return "successful" if (str(sendRequests).find("error") == -1) else "failed"

def getListPost(userID, dataFB): # Lấy danh sách bài viết có trong trang cá nhân của bạn
     
     # The document was written on 28/7/2023 (GMT + 7)
     
     dataForm = formAll(dataFB, "ProfileCometTimelineFeedRefetchQuery", 6375071822546639)
     dataForm["variables"] = json.dumps(
          {
               "UFI2CommentsProvider_commentsKey":"ProfileCometTimelineRoute",
               "afterTime": None,
               "beforeTime": None,
               "count": 3,
               # "cursor":"AQHRmGjjpFA6W-nXG1gGk4XArFpqliWrvDVWbxnM0YeOaZFowRpR1RYJbVsf5em2ItLynh4dvq7k7Vlt_VzeXSg1sXWDbBtmMUBjNFzuDvs4Qw4MtIa_v0S6XlXTyUdbYSyXj6DBPd8n1T7NGEZmpBkz2MPkXPQ2hhg79mS4KgfsrU_co4jQ3iOc74hdgtC3GS1SGOoLgg4mWeeuMatdR2nQWXn_GOg6UtpwxeZv8Pwoyp8ZLJWv92vWp-3xMnKsBTZR3VBWa8aaXlMaYVIgeILVSjRh0Ixjj7fIwbN6C2JSOF4wRcvjosksOV8e1BYLOJlD0Sd0iSKXzRqar9xE6DHjgG-O0rbibGnMzibgyCuOOxl4EiONulQV3i_DDXIbsu4t",
               "displayCommentsContextEnableComment": None,
               "displayCommentsContextIsAdPreview": None,
               "displayCommentsContextIsAggregatedShare": None,
               "displayCommentsContextIsStorySet": None,
               "displayCommentsFeedbackContext": None,
               "feedLocation": "TIMELINE",
               "feedbackSource": 0,
               "focusCommentID": None,
               "memorializedSplitTimeFilter": None,
               "omitPinnedPost": True,
               "postedBy": None,
               "privacy": None,
               "privacySelectorRenderLocation": "COMET_STREAM",
               "renderLocation": "timeline",
               "scale": 3,
               "stream_count": 3,
               "taggedInOnly": None,
               "useDefaultActor": False,
               "id": userID,
               "__relay_internal__pv__IsWorkUserrelayprovider": False,
               "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
               "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
               "__relay_internal__pv__StoriesRingrelayprovider":False
          }
     )
     mainRequests = {
        "headers": Headers(dataFB["cookieFacebook"], dataForm),
        "timeout": 60000,
        "url": "https://www.facebook.com/api/graphql/",
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "data": dataForm,
        "verify": True
     }
     
     sendRequests = requests.post(**mainRequests)
     listFeedbackAndUrlPost = []
     jsonData = json.loads(sendRequests.text.split('{"label":"ProfileCometTimelineFeed_user$defer$ProfileCometTimelineFeed_user_timeline_list_feed_units$page_info"')[0])
     for dataListPost in jsonData["data"]["node"]["timeline_list_feed_units"]["edges"]:
          try:
               urlPost = dataListPost["node"]["comet_sections"]["content"]["story"]["comet_sections"]["context_layout"]["story"]["comet_sections"]["metadata"][0]["story"]["url"]
               feedbackID = dataListPost["node"]["comet_sections"]["content"]["story"]["feedback"]["id"] 
               listFeedbackAndUrlPost.append(urlPost + "|" + feedbackID)
          finally:
               pass
     
     return listFeedbackAndUrlPost
     
def menuTool(IDFB):
     return "≈ ≈ ≈ Facebook BotTool ≈ ≈ ≈\n\n1. Tương tác các bài viết trên Facebook\n2. Lọc bạn bè không tương tác\n3. - \n4. Lấy danh sách bạn bè\n5. Chọn bạn bè\n6. Xoá bạn bè hàng loạt\n7. Tương tác nhóm & Comment bài trên nhóm\n8. Spam tin nhắn liên tục\n\n🔮Bạn đã đăng nhập tài khoản: " + str(IDFB)
     
     