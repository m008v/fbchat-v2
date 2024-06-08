from __facebookToolsV2 import dataGetHome, fbTools
from __messageListenV2 import listeningEvent  # Import the specific class or module you need
from __sendMessage import api
from __uploadAttachments import _uploadAttachment
import datetime, threading, os, json
 
class fbClient:
    def __init__(self, cookies, dataFB):
        self.cookies = cookies
        self.dataFB = dataFB
        self.messageID = None
        self.prefix = "/" # This is the command prompt; when you enter this symbol, the corresponding command will be invoked. Additionally, you can customize it as per your preference (e.g., , . * ! ? etc)
        self.pathFile = ".mqttMessage"
        self.typeAttachment = None
        self.attachmentID = None
        self.typeChat = None # Change this value if you want to send the message to a user instead of a group. If you want to send it to a user, replace it with the value: 'user'
        self.recentReceivedMessages = []

    def setDefaultValue(self):
        self.userID, self.bodyMessage, self.replyToID, self.bodySend, self.commandPlugins, self.typeChat, self.attachmentID, self.typeAttachment= [None] * 8

    def receiveCommandAndSend(self):
        if (self.dataFB["FacebookID"] != self.userID):
             match self.commandPlugins.lower():
                 case "uptime":
                     self.bodySend = "datetime: " + str(datetime.datetime.now())
                 case "hola" | "hello" | "hi":
                     self.bodySend = "Hey,", self.userID
                 case "ping":
                     self.bodySend = "Pong!"
                 case "img":
                     nameAttachment = "NAME PATH IMAGE" # Change the image path here (only image!)
                     uploadAttachment = _uploadAttachment(nameAttachment, self.dataFB) # args=("<nameFile>, dataFB)
                     self.attachmentID = uploadAttachment.get('attachmentID')
                     self.bodySend = 'Your image!'
                     self.typeAttachment = "image" # Change this value to match the attachment.
                     """ WARNING: 
                         This is just an example for sending images. If you want to send other types of attachments,
                         you need to change the value of the variable: typeAttachment.
                         Learn more at: https://github.com/MinhHuyDev/fbchat-v2/blob/main/DOCS.md#uploadAttachmentAndSend
                     """
                 case __:
                     self.bodySend = self.bodyMessage
             mainSend = api()  # Use the specific class or module you imported
             threading.Thread(target=mainSend.send, args=(self.dataFB, self.bodySend, self.replyToID, self.typeAttachment, self.attachmentID, self.typeChat)).start()
             self.setDefaultValue()

    def prefixCheck(self):
        if self.bodyMessage[0] == self.prefix:
            self.commandPlugins = self.bodyMessage.split(self.prefix)[1]
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
                       if (self.bodyMain['type'] != 'thread'): self.typeChat = 'user'
                       self.prefixCheck()
                       self.receiveCommandAndSend()
                       self.setDefaultValue()
               except: # If nothing happens, please replace 'except' with 'finally' to check for errors. 
                   pass
                   

cookies = "<cookie-facebook>"
dataFB = dataGetHome(cookies)
print(dataFB)
_ = fbClient(cookies, dataFB)
_.setDefaultValue()
_.receiveMessage()
print("done!")

""" > A Message from Our Hearts to Our Users < 

Dear Users,

I'm Huy, the owner of the fbchat-v2 project. I'm truly grateful for your time using/reading my project. 
Although it was completed in a short time, I've refined it through numerous tests and 
bug fixes based on user reports, which I greatly appreciate.
Therefore, if you encounter any errors in the project, please report them in the issue section of this repository!
I'd be very thankful for that. Let's be smart and conscious users. Love you all <3

- A note about this source code (main.py): 
It's just a template/sample code to demonstrate:
  + Receiving messages
  + Sending messages
  + Receiving commands from users
  + Sending images
Besides the above, fbchat-v2 has many other powerful features. Please refer to the instructions in DOCS.md to learn how to use them.

"""