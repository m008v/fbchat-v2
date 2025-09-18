FBChat-Remake: Open Source
=======================================
 Dear users, I'm back after a long absence. The project will gradually fix user-reported errors and add new features. Thank you all for sending your reports to me over the past time. (As of August 19, 2025)

Hello, I am **MinhHuyDev**. Firstly, this is my first time remaking such a large source, so there may be *mistakes* in the coding process. I hope users will report any **bugs** in the GitHub issues section here:3

***** *This is not the official API*; Facebook has an API for chatbots available `here <https://developers.facebook.com/docs/messenger-platform/>`_. This library is different in that it uses regular Facebook accounts/cookies as substitutes.

.. image:: https://i.ibb.co/3TWntY6/Picsart-23-08-12-15-11-30-693.jpg

**👽Can't understand English?** You can read the **README** (*VIETNAMESE*): `here <https://github.com/MinhHuyDev/fbchat-v2/blob/main/README.rst>`_

**📢For newcomers**: *Scroll down to the bottom of the page to find* **TUTORIAL (Guide)** *for receiving and sending messages!*

=======================================
Basic Information
=======================================

- **Remade from:** `fbchat (Python) <https://fbchat.readthedocs.io/en/stable/>`_
- **Programming Language:** `Python <https://www.python.org/>`_
- **Developed by:** *Nguyễn Minh Huy*

=======================================
What's New in This Version?
=======================================

**NEW**: Fixed some bugs and made the code more organized

=======================================
Tutorial (Basic Guide)
=======================================

**Firstly**: Users need to install *all* necessary resource packages to use. If you haven't installed them, use the following command:

.. code-block:: bash

  git clone https://github.com/MinhHuyDev/fbchat-v2

**Next**: Create a folder in the main folder you just downloaded from *GitHub* using the following:

*For* **Windows (Command Prompt/PowerShell):**

.. code-block:: bash
  
  cd fbchat-v2/src && type nul > mainBot.py

*For* **Mac/Linux:**

.. code-block:: bash
  
  cd fbchat-v2/src && touch mainBot.py

**Then**: Continue to the **mainBot.py** file, and copy the following code and paste it into the file:

.. code-block:: python

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
     
**🖇️NOTE:** This is just a sample code for receiving and sending messages. If an error occurs, please contribute by fixing it and submit the error information to the *issue*, or contact me directly via **Telegram**
     
After that, go back to the **Terminal/CMD** and run this file with the following command:

.. code-block:: bash

 python mainBot.py

If an error occurs and it cannot be run, try again with the following two commands:

.. code-block:: bash

 python3 mainBot.py

or

.. code-block:: bash

 py mainBot.py

💔If errors persist, please check if Python has been installed on your device. If not, click `here <https://www.python.org/downloads/>`_ to go to the official Python download page.

**🏅Below is an image of successfully running the bot**:

.. image:: https://i.ibb.co/pdbBTWz/nh-ch-p-m-n-h-nh-2024-01-30-130047.png

====================

.. image:: https://i.ibb.co/fvJq87Z/Screenshot-2023-08-18-20-25-51-435-com-offsec-nethunter-kex.png

🫶🏻Thank you for reading this far! If you still have **many questions**, scroll down to find **answers** for yourself :3 Loveeee

=======================================
Frequently Asked Questions
=======================================



You can check common issues or tutorials here: `DOCS.md <https://github.com/MinhHuyDev/fbchat-v2/blob/main/DOCS.md>`_

=======================================
New Version Announcements
=======================================

*📢*: Coming soon...

=======================================
Contact Information
=======================================

- **Facebook:** `Nguyễn Minh Huy :( !! <https://www.facebook.com/Booking.MinhHuyDev>`_
- **Telegram:** `MinhHuyDev <https://t.me/MinhHuyDev>`_
- **Website**: `mhuyz.dev <https://mhuyz.dev>`_
