import json
def Main(contents):

     try: ContentsArgs = contents.split()
     except:
          return json.dumps({
          "results": {
               "command": "ERR",
               "args": {
                    "1": "ERR",
                    "2": "ERR",
                    "3": "ERR",
                    "4": "ERR",
                    "full": "ERR"
               }
          }
     }, ensure_ascii=False)

     if len(ContentsArgs) >= 5:
         Args1 = ContentsArgs[1]
         Args2 = ContentsArgs[2]
         Args3 = ContentsArgs[3]
         Args4 = " ".join([ContentsArgs[i] for i in range(4, len(ContentsArgs))])
         ArgsFull = f"{Args1} {Args2} {Args3} {Args4}"
     elif len(ContentsArgs) == 4:
         Args1 = ContentsArgs[1]
         Args2 = ContentsArgs[2]
         Args3 = ContentsArgs[3]
         Args4 = None
         ArgsFull = f"{Args1} {Args2} {Args3}"
     elif len(ContentsArgs) == 3:
         Args1 = ContentsArgs[1]
         Args2 = ContentsArgs[2]
         Args3 = None
         Args4 = ""
         ArgsFull = f"{Args1} {Args2}"
     elif len(ContentsArgs) == 2:
         Args1 = ContentsArgs[1]
         Args2 = None
         Args3 = None
         Args4 = None
         ArgsFull = Args1
     else:
         Args1 = None
         Args2 = None
         Args3 = None
         Args4 = None
         ArgsFull = None
     
     return json.dumps({
          "results": {
               "command": ContentsArgs[0],
               "args": {
                    "1": Args1,
                    "2": Args2,
                    "3": Args3,
                    "4": Args4,
                    "full": ArgsFull
               }
          }
     }, ensure_ascii=False)

     
print(Main(",help 1 2 3 4 huy dz"))

