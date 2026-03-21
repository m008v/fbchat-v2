import requests, json, time, datetime
from _core._utils import formAll, mainRequests

def createItem(dataFB, nameItem, brandItem, priceItem, currencyItem, decriptionItem, hashtagList, typeItem, photoIDList, locationSeller):
    
    # Được lấy dữ liệu và viết vào lúc: 22:25 Thứ 3, ngày 10/10/2023. Tác giả: MinhHuyDev
    # Thank you @syrex1013 (Github) very much for your idea
    # Thank you @tranngocminh230791 (Github) very much for categoryDict
    
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
        "Home & Garden": {
            "Tools": 2171028376552553,
            "Furniture": 1583634935226685,
            "Household": 1569171756675761,
            "Garden": 800089866739547,
            "Appliances": 678754142233400
        },
        "Entertainment": {
            "Video Games": 686977074745292,
            "Books Movies&Music": 613858625416355
        },
        "Clothing&Accessories": {
            "Bags & Luggage": 1567543000236608,
            "Women's clothing & shoes": 1266429133383966,
            "Men's clothing & shoes": 931157863635831,
            "Jewelry & Accessories": 214968118845643
        },
        "Family": {
            "Health & beauty": 1555452698044988,
            "Pet Supplies": 1550246318620997,
            "Baby & kids": 624859874282116,
            "Toys & Games": 606456512821491
        },
        "Electronics": {
            "Electronics & computers": 1792291877663080,
            "Mobile phones": 1557869527812749,
        },
        "Hobbies": {
            "Bicycles": 1658310421102081,
            "Arts & Crafts": 1534799543476160,
            "Sports & Outdoors": 1383948661922113,
            "Auto parts": 757715671026531,
            "Musical Instruments": 676772489112490,
            "Antiques & Collectibles": 393860164117441,
        },
        "Classifieds": {
            "Garage Sale": 1834536343472201,
            "Miscellaneous": 895487550471874
        },
        # There are more options than that... Please continue to develop it for me ¯⁠\⁠_⁠(⁠ツ⁠)⁠_⁠/⁠¯
    }
    
    dataForm = formAll(dataFB, "useCometMarketplaceListingCreateMutation", 5033081016747999)
    dataForm["variables"] = json.dumps(
        {
            "input": {
                    "client_mutation_id": "3",
                    "actor_id": dataFB["FacebookID"],
                    "attribution_id_v2": f"CometMarketplaceComposerRoot.react,comet.marketplace.composer,unexpected,{int(time.time() * 1000)},{dataFB['jazoest']},1606854132932955,;CometMarketplaceComposerRoot.react,comet.marketplace.composer,via_cold_start,{int(time.time() * 1000)},{dataFB['jazoest']},1606854132932955,",
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
    
    sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
    
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

def getInformationProductItemMarketPlace(dataFB, idProductItem):
     
        # Được lấy dữ liệu và viết vào lúc: 22:25 Thứ 3, ngày 10/10/2023. Tác giả: MinhHuyDev
        # Thank you @syrex1013 (Github) very much for your idea

    
        """Args:
            idProductItem: ID of item (eg. 1176770623712137) | typeInput: str
        """
        
        #Note: How to get ID of item? It's right on the product link: https://www.facebook.com/marketplace/item/1176770623712137/ | ID item: 1176770623712137
        
        dataForm = formAll(dataFB, "MarketplacePDPContainerQuery", 6720440741405337)
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
    
        sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/api/graphql/", dataForm, dataFB["cookieFacebook"])).text)
        
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