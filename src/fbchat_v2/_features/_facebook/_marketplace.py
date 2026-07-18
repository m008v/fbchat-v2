from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from fbchat_v2._core._utils import formAll, post_form_json, post_form_json_async

_URL = "https://www.facebook.com/api/graphql/"
_CREATE_DOC_ID = 5033081016747999
_DETAIL_DOC_ID = 6720440741405337
_CATEGORY_IDS = {
    "Tools": 2171028376552553,
    "Furniture": 1583634935226685,
    "Household": 1569171756675761,
    "Garden": 800089866739547,
    "Appliances": 678754142233400,
    "Video Games": 686977074745292,
    "Books Movies&Music": 613858625416355,
    "Bags & Luggage": 1567543000236608,
    "Women's clothing & shoes": 1266429133383966,
    "Men's clothing & shoes": 931157863635831,
    "Jewelry & Accessories": 214968118845643,
    "Health & beauty": 1555452698044988,
    "Pet Supplies": 1550246318620997,
    "Baby & kids": 624859874282116,
    "Toys & Games": 606456512821491,
    "Electronics & computers": 1792291877663080,
    "Mobile phones": 1557869527812749,
    "Bicycles": 1658310421102081,
    "Arts & Crafts": 1534799543476160,
    "Sports & Outdoors": 1383948661922113,
    "Auto parts": 757715671026531,
    "Musical Instruments": 676772489112490,
    "Antiques & Collectibles": 393860164117441,
    "Garage Sale": 1834536343472201,
    "Miscellaneous": 895487550471874,
}


def _error_message(payload: dict[str, Any], fallback: str) -> str:
    errors = payload.get("errors") or []
    if errors and isinstance(errors[0], dict) and errors[0].get("message"):
        return str(errors[0]["message"])
    return fallback


def _validate_location(location: dict[str, Any]) -> tuple[float, float]:
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "locationSeller phải có latitude và longitude dạng số."
        ) from error
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Tọa độ người bán nằm ngoài phạm vi hợp lệ.")
    return latitude, longitude


def _build_create_form(
    dataFB: dict[str, Any],
    nameItem: str,
    brandItem: str,
    priceItem: int | float | str,
    currencyItem: str,
    decriptionItem: str,
    hashtagList: list[str],
    typeItem: str,
    photoIDList: list[str | int],
    locationSeller: dict[str, Any],
) -> dict[str, Any]:
    if typeItem not in _CATEGORY_IDS:
        raise ValueError(
            f"Danh mục không hợp lệ: {typeItem}. Hỗ trợ: {', '.join(sorted(_CATEGORY_IDS))}."
        )
    if not nameItem.strip():
        raise ValueError("Tên sản phẩm không được để trống.")
    if not photoIDList:
        raise ValueError("Marketplace yêu cầu ít nhất một ảnh sản phẩm.")
    try:
        numeric_price = float(priceItem)
    except (TypeError, ValueError) as error:
        raise ValueError("Giá sản phẩm phải là số.") from error
    if numeric_price < 0:
        raise ValueError("Giá sản phẩm không được âm.")
    latitude, longitude = _validate_location(locationSeller)

    attribute_data = {
        "vt_attributes_free_form": {"372885700169792": brandItem},
        "vt_attributes_normalized": {},
        "condition": "new",
        "brand": brandItem,
    }
    now_ms = int(time.time() * 1000)
    data_form = formAll(
        dataFB, "useCometMarketplaceListingCreateMutation", _CREATE_DOC_ID
    )
    data_form["variables"] = json.dumps(
        {
            "input": {
                "client_mutation_id": "3",
                "actor_id": dataFB["FacebookID"],
                "attribution_id_v2": (
                    "CometMarketplaceComposerRoot.react,comet.marketplace.composer,"
                    f"via_cold_start,{now_ms},{dataFB['jazoest']},1606854132932955,"
                ),
                "audience": {
                    "marketplace": {"marketplace_id": str(_CATEGORY_IDS[typeItem])}
                },
                "data": {
                    "common": {
                        "attribute_data_json": json.dumps(
                            attribute_data, separators=(",", ":")
                        ),
                        "category_id": _CATEGORY_IDS[typeItem],
                        "commerce_shipping_carrier": None,
                        "commerce_shipping_carriers": [],
                        "comparable_price": "null",
                        "cost_per_additional_item": None,
                        "delivery_types": ["IN_PERSON"],
                        "description": {"text": decriptionItem},
                        "draft_type": None,
                        "hidden_from_friends_visibility": "VISIBLE_TO_EVERYONE",
                        "is_personalization_required": None,
                        "is_preview": False,
                        "item_price": {
                            "currency": currencyItem.upper(),
                            "price": str(priceItem),
                        },
                        "latitude": latitude,
                        "longitude": longitude,
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
                        "title": nameItem.strip(),
                        "variants": [],
                        "video_ids": [],
                        "xpost_target_ids": [],
                        "photo_ids": [str(photo_id) for photo_id in photoIDList],
                    }
                },
            }
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_create_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        story = payload["data"]["marketplace_listing_create"]["listing"]["story"]
        return {
            "success": 1,
            "messages": "Tạo bài bán hàng thành công!",
            "data": {"url": story["url"], "id": story["id"]},
        }
    except (KeyError, TypeError):
        return {
            "error": 1,
            "messages": _error_message(
                payload, "Facebook không trả về bài bán hàng đã tạo."
            ),
        }


def _build_detail_form(
    dataFB: dict[str, Any], idProductItem: str | int
) -> dict[str, Any]:
    if not str(idProductItem).strip():
        raise ValueError("ID sản phẩm không được để trống.")
    data_form = formAll(dataFB, "MarketplacePDPContainerQuery", _DETAIL_DOC_ID)
    data_form["variables"] = json.dumps(
        {
            "UFI2CommentsProvider_commentsKey": "MarketplacePDP",
            "feedbackSource": 56,
            "feedLocation": "MARKETPLACE_MEGAMALL",
            "referralCode": "marketplace_top_picks",
            "scale": 3,
            "should_show_new_pdp": False,
            "targetId": str(idProductItem),
            "useDefaultActor": False,
            "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False,
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_detail_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        page = payload["data"]["viewer"]["marketplace_product_details_page"]
        renderable = page["marketplace_listing_renderable_target"]
        target = page["target"]
        actor = target["story"]["actors"][0]
        created_at = datetime.fromtimestamp(
            int(target["creation_time"]), tz=timezone.utc
        ).isoformat()
        return {
            "success": 1,
            "messages": "Lấy thông tin sản phẩm thành công!",
            "data": {
                "productName": renderable["marketplace_listing_title"],
                "locationSeller": renderable["location"],
                "productDescription": target["redacted_description"]["text"],
                "productPrice": {
                    "price": target["listing_price"]["amount"],
                    "currency": target["listing_price"]["currency"],
                },
                "nameSeller": actor["name"],
                "idSeller": actor["id"],
                "urlProduct": target["story"]["url"],
                "createdAt": created_at,
            },
        }
    except (KeyError, TypeError, IndexError, ValueError, OSError):
        return {
            "error": 1,
            "messages": _error_message(payload, "Không thể đọc thông tin sản phẩm."),
        }

async def createItem(
    dataFB: dict[str, Any],
    nameItem: str,
    brandItem: str,
    priceItem: int | float | str,
    currencyItem: str,
    decriptionItem: str,
    hashtagList: list[str],
    typeItem: str,
    photoIDList: list[str | int],
    locationSeller: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    payload = await post_form_json_async(
        _URL,
        _build_create_form(
            dataFB,
            nameItem,
            brandItem,
            priceItem,
            currencyItem,
            decriptionItem,
            hashtagList,
            typeItem,
            photoIDList,
            locationSeller,
        ),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_create_result(payload)


def _getInformationProductItemMarketPlace_blocking(
    dataFB: dict[str, Any],
    idProductItem: str | int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    payload = post_form_json(
        _URL,
        _build_detail_form(dataFB, idProductItem),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_detail_result(payload)


async def getInformationProductItemMarketPlace(
    dataFB: dict[str, Any],
    idProductItem: str | int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    payload = await post_form_json_async(
        _URL,
        _build_detail_form(dataFB, idProductItem),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_detail_result(payload)
