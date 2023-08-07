import json

def Main(contents): 
    try:
        ContentsArgs = contents.split()
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

    num_args = len(ContentsArgs) - 1
    ArgsFull = " ".join(ContentsArgs[1:])
    Args1 = ContentsArgs[1] if num_args >= 1 else None
    Args2 = ContentsArgs[2] if num_args >= 2 else None 
    Args3 = ContentsArgs[3] if num_args >= 3 else None
    Args4 = " ".join([ContentsArgs[i] for i in range(4, len(ContentsArgs))]) if num_args >= 4 else None

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


print(Main(",help 1 2 3"))
