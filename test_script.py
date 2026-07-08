import asyncio
import os
import sys
import threading
import time

# Đảm bảo import được từ thư mục src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from _core._session import dataGetHome_async
from _messaging._send import api
from _messaging._reactions import func_async as reactions_async
from _messaging._unsend import func_async as unsend_async
from _messaging._attachments import func_async as attachments_async
from _messaging._listening_e2ee import listeningE2EEEvent
from _messaging._send_e2ee import api as E2EESender
from _messaging._editMessage import func_async as edit_message_async
from _messaging._changeTheme import func_async as change_theme_async
from _messaging._createNotes import func_async as create_notes_async
from _messaging._message_requests import func_async as message_requests_async
from _features._facebook._get_user_info import func_async as get_user_info_async
from _features._facebook._search import func_async as search_facebook_async
from _features._thread._changeEmoji import func_async as change_emoji_async
from _features._thread._changeNickname import func_async as change_nickname_async

def on_e2ee_message(msg):
    # Callback xử lý tin nhắn E2EE (từ Bridge trả về event có dạng {'type': '...', 'data': {...}})
    msg_type = msg.get('type')
    if msg_type in ('message', 'e2eeMessage'):
        data = msg.get('data', {})
        print(f"\n[E2EE Listener] Nhận được tin nhắn ({msg_type}) từ {data.get('senderId', 'Unknown')}:")
        print(f"Nội dung: {data.get('text')}")

async def main():
    cookie = 'datr=-cZfaVKhV1X4Vyz8MYNOzcDT; sb=-cZfaXmr3bC0O-Uhcdo_KyXz; ps_l=1; ps_n=1; pas=61583942146559%3AVfN5tgl8z5; vpd=v1%3B866x864x2; wl_cbv=v2%3Bclient_version%3A3161%3Btimestamp%3A1778829826; c_user=61583942146559; fr=2QRUPzZNnien9qWba.AWe3lw1nhu1_pMcgWTu_ceEeF1aWoJ_Dj_-Gb82IylfuJ0C4Tjc.BqTa4c..AAA.0.0.BqTa4c.AWe2X8NSCRwm88ip1LXJfhcG8mo; xs=38%3AEYXLGGmOsb7OYQ%3A2%3A1782534136%3A-1%3A-1%3A%3AAcx6W28rxD5coeRie3agvb6_PZ_fSAZIubkJSp38100; wd=390x844; dpr=3; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1783475747210%2C%22v%22%3A1%7D'
            
    if not cookie:
        print("❌ Lỗi: Vui lòng set biến môi trường FB_COOKIE hoặc dán cookie vào file cookie.txt.")
        return
        
    print("1. Đang khởi tạo session từ Cookie...")
    dataFB = await dataGetHome_async(cookie)
    if not dataFB:
        print("❌ Login failed: Không thể parse cookie hoặc cookie hết hạn.")
        return
    print(f"✅ Login success. Facebook ID: {dataFB.get('FacebookID')}")

    target_id = '24922122864142978'

    print(f"\n2. Đang gửi tin nhắn thường đến {target_id}...")
    send_api_instance = api()
    send_res = await send_api_instance.send_async(dataFB, "Test từ fbchat-v2 Async/Await!", target_id, typeChat="user")
    print(f"Kết quả Send: {send_res}")
    
    payload_data = send_res.get("payload") or {}
    message_id = payload_data.get("messageID")
    if message_id:
        print(f"\n3. Đang reaction '👍' vào {message_id}...")
        react_res = await reactions_async(dataFB, "add", message_id, "👍")
        print(f"Kết quả React: status {react_res.status_code}")

        print(f"\n4. Đang sửa tin nhắn {message_id}...")
        edit_res = await edit_message_async(dataFB, message_id, "Nội dung đã được sửa (Async)!")
        print(f"Kết quả Edit: {edit_res}")
        print("-> Tạm dừng 3 giây để bạn kịp xem tin nhắn đã sửa trước khi thu hồi...")
        await asyncio.sleep(3)

        print(f"\n5. Đang unsend tin nhắn {message_id}...")
        unsend_res = await unsend_async(message_id, dataFB)
        print(f"Kết quả Unsend: {unsend_res}")
        
    print("\n6. Test upload attachments...")
    with open("test_dummy.txt", "w") as f:
        f.write("Hello dummy!")
    att_res = await attachments_async("test_dummy.txt", dataFB)
    print(f"Kết quả Upload Attachment: {att_res}")
    if os.path.exists("test_dummy.txt"): os.remove("test_dummy.txt")

    print("\n7. Test thay đổi Theme...")
    theme_res = await change_theme_async(dataFB, target_id, "2442142322678320")
    print(f"Kết quả Change Theme: {theme_res}")

    print("\n8. Test tạo Note...")
    note_res = await create_notes_async(dataFB, action="create", text="Test note từ fbchat-v2 Async")
    print(f"Kết quả Create Note: {note_res}")
    if note_res.get("data") and note_res["data"].get("note_create"):
        note_id = note_res["data"]["note_create"]["note"]["id"]
        print(f"-> Đang xoá Note vừa tạo (ID: {note_id})...")
        await create_notes_async(dataFB, action="delete", noteID=note_id)

    print("\n9. Lấy danh sách Message Requests...")
    req_res = await message_requests_async(dataFB)
    print(f"Kết quả Message Requests: có {len(req_res.get('data', []))} requests (tối đa in 1).")
    if req_res.get("data"):
        print(req_res["data"][0])

    print("\n10. Test Get User Info (Facebook Feature)...")
    try:
        user_info = await get_user_info_async(dataFB, dataFB["FacebookID"])
        print(f"Kết quả Get User Info: {user_info}")
    except Exception as e:
        print(f"Lỗi Get User Info: {e}")

    print("\n11. Test Change Emoji (Thread Feature)...")
    try:
        emoji_res = await change_emoji_async(dataFB, target_id, "😎")
        print(f"Kết quả Change Emoji: {emoji_res}")
    except Exception as e:
        print(f"Lỗi Change Emoji: {e}")

    print("\n12. Test Search (Facebook Feature)...")
    try:
        search_res = await search_facebook_async(dataFB, "Mark Zuckerberg")
        print(f"Kết quả Search Facebook: {search_res}")
    except Exception as e:
        print(f"Lỗi Search Facebook: {e}")

    print("\n13. Test Change Nickname (Thread Feature)...")
    try:
        nick_res = await change_nickname_async(dataFB, target_id, dataFB["FacebookID"], "Test Bot Nickname")
        print(f"Kết quả Change Nickname: {nick_res}")
    except Exception as e:
        print(f"Lỗi Change Nickname: {e}")

    print("\n14. Khởi động E2EE Listener & Gửi E2EE...")
    listener = listeningE2EEEvent(dataFB)
    listener.on_message(on_e2ee_message)
    listener_thread = threading.Thread(target=listener.connect_mqtt, daemon=True)
    listener_thread.start()
    
    print("⏳ Đang đợi Listener E2EE khởi động (3s)...")
    time.sleep(3)
    
    sender = E2EESender(listener=listener)
    print(f"\n7. Đang gửi tin nhắn E2EE đến {target_id}...")
    try:
        e2ee_res = sender.send_to_user(9209278, "Test E2EE từ fbchat-v2!")
        print(f"Kết quả Send E2EE: {e2ee_res}")
    except Exception as e:
        print(f"Lỗi Send E2EE: {e}")
    
    print("\n⏳ Đang đợi nhận tin nhắn trong 5 giây (nếu test được chat hãy chat vào bot).")
    time.sleep(5)
    
    print("Dừng Listener...")
    listener.stop()
    print("Xong bài test toàn diện!")

if __name__ == "__main__":
    asyncio.run(main())
