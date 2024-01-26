from __facebookToolsV2 import dataGetHome, fbTools
from __messageListenV2 import listeningEvent  # Import the specific class or module you need
from __sendMessage import api
import datetime, threading, os, json
 
class fbClient:
    def __init__(self, cookies, dataFB):
        self.cookies = cookies
        self.dataFB = dataFB
        self.messageID = None
        self.prefix = "/" # This is the command prompt; when you enter this symbol, the corresponding command will be invoked. Additionally, you can customize it as per your preference (e.g., , . * ! ? etc)
        self.pathFile = ".mqttMessage"
        self.recentReceivedMessages = []

    def setDefaultValue(self):
        self.userID, self.bodyMessage, self.replyToID, self.bodySend, self.commandPlugins = [None] * 5

    def receiveCommandAndSend(self):
        if (self.dataFB["FacebookID"] != self.userID):
             match self.commandPlugins.lower():
                 case "uptime":
                     self.bodySend = "datetime: " + str(datetime.datetime.now())
                 case "hola" | "hello" | "hi":
                     self.bodySend = "Hey,", self.userID
                 case "ping":
                     self.bodySend = "Pong!"
                 case __:
                     self.bodySend = self.bodyMessage
             mainSend = api()  # Use the specific class or module you imported
             threading.Thread(target=mainSend.send, args=(self.dataFB, self.bodySend, self.replyToID)).start()
             self.setDefaultValue()

    def prefixCheck(self):
        if self.bodyMessage[0] == self.prefix:
            self.commandPlugins = self.bodyMessage.split(',')[1]
        else:
            self.commandPlugins = self.bodyMessage
          

    def receiveMessage(self):
        self.fbt = fbTools(self.dataFB, 0)
        mainReceiveMessage = listeningEvent(self.fbt, self.dataFB)  # Use the specific class or module you imported
        mainReceiveMessage.get_last_seq_id()
        threading.Thread(target=mainReceiveMessage.connect_mqtt, args=()).start()
        """
        Why am I using Threading here? 
        Because when calling connect_mqtt(), the programs after it won't be able to run 
        as it continuously connects to the Facebook server. To overcome this, I've used threading 
        to make it run concurrently with other functions!
        """
        while 1:
           if os.path.isfile(self.pathFile):
               try:
                   self.bodyMain = json.loads(open(self.pathFile, "r", encoding="utf-8").read())
                   # print(f"{self.bodyMain['messageID']} != {self.messageID} {self.bodyMain['messageID'] != self.messageID}")
                   if self.bodyMain['messageID'] != self.messageID:
                       self.userID = self.bodyMain['userID']
                       self.messageID = self.bodyMain['messageID']
                       self.bodyMessage = self.bodyMain['body']
                       self.replyToID = self.bodyMain['replyToID']
                       print(f"> userID: {self.userID}\n> messageID: {self.messageID}\n> messageContents: {self.bodyMessage}\n> From {self.bodyMain['type']}ID: {self.replyToID}\n- - - - -")
                       self.prefixCheck()
                       self.receiveCommandAndSend()
                       self.setDefaultValue()
               except:
                   pass

cookies = "this is set Cookie Facebook"
dataFB = dataGetHome(cookies)
_ = fbClient(cookies, dataFB)
_.setDefaultValue()
_.receiveMessage()
print("done!")
