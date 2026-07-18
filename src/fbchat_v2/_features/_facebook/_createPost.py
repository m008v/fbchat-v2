from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from fbchat_v2._core._utils import formAll, post_form_json_async

_URL = "https://www.facebook.com/api/graphql/"
_DOC_ID = 6534257523262244


def _build_form(
    dataFB: dict[str, Any], newContents: str, attachmentID: str | int | None
) -> dict[str, Any]:
    if not str(newContents).strip():
        raise ValueError("Nội dung bài viết không được để trống.")
    if attachmentID is not None:
        raise NotImplementedError(
            "attachmentID chưa được hỗ trợ cho ComposerStoryCreateMutation; "
            "không còn âm thầm bỏ qua tệp đính kèm."
        )

    data_form = formAll(dataFB, "ComposerStoryCreateMutation", _DOC_ID)
    data_form["variables"] = json.dumps(
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
                        "tag_expansion_state": "UNSPECIFIED",
                    }
                },
                "message": {"ranges": [], "text": str(newContents)},
                "with_tags_ids": [],
                "inline_activities": [],
                "explicit_place_id": "0",
                "text_format_preset_id": "0",
                "logging": {"composer_session_id": dataFB["sessionID"]},
                "navigation_data": {
                    "attribution_id_v2": (
                        "ProfileCometTimelineListViewRoot.react,"
                        f"comet.profile.timeline.list,tap_bookmark,{int(time.time() * 1000)},"
                        f"{dataFB['jazoest']},{dataFB['FacebookID']}"
                    )
                },
                "tracking": "[null]",
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": "1",
            },
            "displayCommentsFeedbackContext": None,
            "displayCommentsContextEnableComment": None,
            "displayCommentsContextIsAdPreview": None,
            "displayCommentsContextIsAggregatedShare": None,
            "displayCommentsContextIsStorySet": None,
            "feedLocation": "TIMELINE",
            "focusCommentID": None,
            "scale": str(round(random.random() * 1024)),
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "timeline",
            "useDefaultActor": False,
            "inviteShortLinkKey": None,
            "isFeed": False,
            "isFundraiser": False,
            "isFunFactPost": False,
            "isGroup": False,
            "isEvent": False,
            "isTimeline": True,
            "isSocialLearning": False,
            "isPageNewsFeed": False,
            "isProfileReviews": False,
            "isWorkSharedDraft": False,
            "UFI2CommentsProvider_commentsKey": "ProfileCometTimelineRoute",
            "hashtag": None,
            "canUserManageOffers": False,
            "__relay_internal__pv__IsWorkUserrelayprovider": False,
            "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
            "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
            "__relay_internal__pv__StoriesRingrelayprovider": False,
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        url = payload["data"]["story_create"]["story"]["url"]
    except (KeyError, TypeError):
        errors = payload.get("errors") or []
        message = (
            errors[0].get("message") if errors and isinstance(errors[0], dict) else None
        )
        return {
            "error": 1,
            "messages": message or "Facebook không trả về bài viết đã tạo.",
        }
    return {"success": 1, "messages": "Tạo bài viết thành công!", "urlPost": url}



async def func(
    dataFB: dict[str, Any],
    newContents: str,
    attachmentID: str | int | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, newContents, attachmentID),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_result(payload)
