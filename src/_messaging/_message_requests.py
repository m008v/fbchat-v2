import requests, json
from _core._utils import formAll, mainRequests

def func(dataFB): # Lấy danh sách tin nhắn chờ
          
          # Được lấy dữ liệu và viết vào lúc: 21:43 Thứ 4, ngày 05/07/2023. Tác giả: MinhHuyDev
          # DATETIME - UPDATE: 13/02/2024 13:21
                    
          dataForm = formAll(dataFB, requireGraphql=0)
          dataForm["queries"] = json.dumps({
               "o0": {
                    "doc_id": "3336396659757871",
                    "query_params": {
                         "limit": 10000,
                         "before": None,
                         "tags": ["PENDING"], # INBOX, PENDING, ARCHIVED
                         "includeDeliveryReceipts": False,
                         "includeSeqID": True,
                    }
               }
          })
          
          sendRequests = requests.post(**mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, dataFB["cookieFacebook"]))
          # return sendRequests.text.split("{\"successful_results\"")[0]
          dataGet = json.loads(sendRequests.text.split('{"successful_results"')[0])
          PendingList = dataGet['o0']['data']['viewer']['message_threads']['nodes']
          dictExportData = {"data":{}}
          total = 0
          for i in PendingList:
               over = i['last_message']['nodes']
               try:
                    contentMessage, senderID, timestamp_precise = over[0]['snippet'], over[0]['message_sender']['messaging_actor']['id'], over[0]['timestamp_precise']
                    dictExportData[total] = {'senderID': senderID, 'snippet': contentMessage, 'timestamp_precise': timestamp_precise}
                    total += 1
               except (IndexError, KeyError, TypeError):
                    pass
          dictExportData['total_count'] = total
          return {
               "success": 1,
               "messageRequests": json.dumps(dictExportData, indent=5)
          }