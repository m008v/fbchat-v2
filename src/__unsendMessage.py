import requests, json
from utils import formAll, mainRequests
 
def _unsend(messageID, dataFB):

     dataForm = formAll(dataFB, requireGraphql=False)
     dataForm["message_id"] = messageID

     sendRequests = json.loads(requests.post(**mainRequests("https://www.facebook.com/messaging/unsend_message/", dataForm, dataFB["cookieFacebook"])).text.split("for (;;);")[1])

     if (sendRequests.get("error")):
          return Exception({"error": str(sendRequests)})
     return {
          "success": 1,
          "messages": "Thu hồi tin nhắn thành công."
     }

# completed at 09:36 30/06/2023 | last updated at 19:50 13/12/2023
