from __future__ import annotations

import json
import random
from typing import Any

import httpx

from _core._utils import (
    formAll,
    generate_client_id,
    post_form_json_async,
)

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(dataFB: dict[str, Any], keywordSearch: str) -> dict[str, Any]:
    keyword = str(keywordSearch).strip()
    if not keyword:
        raise ValueError("Từ khoá tìm kiếm không được để trống.")
    data_form = formAll(
        dataFB, "SearchCometResultsInitialResultsQuery", 6866854183333610
    )
    data_form["variables"] = json.dumps(
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
                    "watch_config": None,
                },
                "context": {"bsid": generate_client_id(), "tsid": str(random.random())},
                "experience": {
                    "encoded_server_defined_params": None,
                    "fbid": None,
                    "type": "GLOBAL_SEARCH",
                },
                "filters": [],
                "text": keyword,
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
            "__relay_internal__pv__StoriesRingrelayprovider": False,
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any], keyword: str) -> dict[str, Any]:
    try:
        edges = payload["data"]["serpResponse"]["results"]["edges"]
    except (KeyError, TypeError):
        message = ((payload.get("errors") or [{}])[0]).get("message")
        return {"error": 1, "messages": message or "Response tìm kiếm không hợp lệ."}

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for edge in edges if isinstance(edges, list) else []:
        strategies = (
            (
                (edge.get("relay_rendering_strategy") or {}).get(
                    "result_rendering_strategies"
                )
                or []
            )
            if isinstance(edge, dict)
            else []
        )
        for strategy in strategies:
            profile = (
                ((strategy.get("view_model") or {}).get("profile") or {})
                if isinstance(strategy, dict)
                else {}
            )
            user_id = str(profile.get("id") or "")
            if not user_id or user_id in seen_ids:
                continue
            seen_ids.add(user_id)
            results.append(
                {"name": profile.get("name"), "id": user_id, "url": profile.get("url")}
            )
            if len(results) == 5:
                break
        if len(results) == 5:
            break

    lines = [
        f"{index}. {item.get('name')} — {item.get('id')} — {item.get('url')}"
        for index, item in enumerate(results, 1)
    ]
    return {
        "success": 1,
        "searchResults": f"Tìm kiếm Facebook: {keyword}\n"
        + "\n".join(lines)
        + f"\nSố lượng kết quả: {len(results)}",
        "searchResultsDict": results,
    }



async def func(
    dataFB: dict[str, Any],
    keywordSearch: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        keyword = str(keywordSearch).strip()
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, keyword),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, keyword)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
