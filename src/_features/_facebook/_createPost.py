import json, requests, time, json, random
from _core._utils import formAll, mainRequests

def func(dataFB, newContents, attachmentID=None): # Tạo bài viết trên Facebook
    
    # Được lấy dữ liệu và viết vào lúc: 09:40 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
    """Args:
        newContents: content of post to create (eg. MinhHuy create new post!) | typeInput: str
        attachmentID: Coming soon....
    """
    
    dataForm = formAll(dataFB, "ComposerStoryCreateMutation", 6534257523262244)
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
                        "composer_session_id": dataFB["sessionID"]
                    },
                    "navigation_data": {
                        "attribution_id_v2": f"ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,tap_bookmark,{int(time.time() * 1000)},{dataFB['jazoest']},{dataFB['FacebookID']}"
                    },
                    "tracking": "[null]",
                    "actor_id": dataFB["FacebookID"],
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
                    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
    
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