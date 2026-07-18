import asyncio
import os
import struct
import sys
import threading
import time
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Đảm bảo import được từ thư mục src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from _core._session import dataGetHome
from _messaging._send import api
from _messaging._reactions import func as reactions_async
from _messaging._unsend import func as unsend_async
from _messaging._attachments import func as attachments_async
from _messaging._listening_e2ee import listeningE2EEEvent
from _messaging._send_e2ee import api as E2EESender
from _messaging._editMessage import func as edit_message_async
from _messaging._changeTheme import func as change_theme_async
from _messaging._createNotes import func as create_notes_async
from _messaging._message_requests import func as message_requests_async
from _features._facebook._get_user_info import func as get_user_info_async
from _features._facebook._search import func as search_facebook_async
from _features._facebook._notification import func as get_notification_async
from _features._facebook._changeBio import func as change_bio_async
from _features._thread._changeEmoji import func as change_emoji_async
from _features._thread._changeNickname import func as change_nickname_async
from _features._thread._all_thread_data import func as all_thread_data_async
from _features._thread._changeNameThread import func as change_name_thread_async
from _features._facebook._createPost import func as create_post_async
from _features._facebook._blocking import func as blocking_async
from _features._facebook._professional import func as professional_async
from _features._facebook._marketplace import createItem as marketplace_create_async

def read_cookie():
    cookie = os.environ.get("FB_COOKIE", "").strip()
    if cookie:
        return cookie
    cookie_file = Path("cookie.txt")
    if cookie_file.is_file():
        return cookie_file.read_text(encoding="utf-8").strip()
    return ""


def png_chunk(chunk_type, data):
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def build_sample_png(width=96, height=96):
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(
                (
                    32 + (x * 160 // max(width - 1, 1)),
                    72 + (y * 120 // max(height - 1, 1)),
                    180,
                )
            )
        rows.append(bytes(row))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + png_chunk(b"IEND", b"")
    )


def ensure_sample_attachment():
    sample_dir = Path(".tmp")
    sample_dir.mkdir(exist_ok=True)
    sample_path = sample_dir / "fbchat-upload-sample.png"
    sample_path.write_bytes(build_sample_png())
    return sample_path.resolve()


def get_attachment_path():
    raw_path = (
        sys.argv[1].strip()
        if len(sys.argv) > 1 and sys.argv[1].strip()
        else os.environ.get("FBCHAT_ATTACHMENT_FILE", "").strip()
    )
    if not raw_path:
        path = ensure_sample_attachment()
        print(f"Không truyền attachment, dùng ảnh sample tạm: {path}")
        return path
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file attachment: {path}")
    return path


def on_e2ee_message(msg):
    # Callback xử lý tin nhắn E2EE (từ Bridge trả về event có dạng {'type': '...', 'data': {...}})
    msg_type = msg.get('type')
    if msg_type in ('message', 'e2eeMessage'):
        data = msg.get('data', {})
        print(f"\n[E2EE Listener] Nhận được tin nhắn ({msg_type}) từ {data.get('senderId', 'Unknown')}:")
        print(f"Nội dung: {data.get('text')}")

async def main():
    cookie = read_cookie()
            
    if not cookie:
        print("❌ Lỗi: Vui lòng set biến môi trường FB_COOKIE hoặc dán cookie vào file cookie.txt.")
        return
        
    print("1. Đang khởi tạo session từ Cookie...")
    dataFB = await dataGetHome(cookie)
    if not dataFB:
        print("❌ Login failed: Không thể parse cookie hoặc cookie hết hạn.")
        return
    print(f"✅ Login success. Facebook ID: {dataFB.get('FacebookID')}")

    target_id = '24922122864142978'

    print(f"\n2. Đang gửi tin nhắn thường đến {target_id}...")
    send_api_instance = api()
    send_res = await send_api_instance.send(dataFB, "Test từ fbchat-v2 Async/Await!", target_id, typeChat="user")
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
    try:
        attachment_path = get_attachment_path()
        att_res = await attachments_async(
            str(attachment_path),
            dataFB,
            include_error=True,
        )
        print(f"Kết quả Upload Attachment: {att_res}")
        if not att_res or not att_res.get("attachmentID"):
            raise RuntimeError("Upload không trả attachmentID. Cookie/file/endpoint đang có vấn đề.")

        attachment_send_type = att_res.get("typeAttachment") or "file"
        attachment_send_res = await send_api_instance.send(
            dataFB,
            f"Attachment test: {attachment_path.name}",
            target_id,
            typeAttachment=attachment_send_type,
            attachmentID=att_res["attachmentID"],
            typeChat="user",
        )
        print(f"Kết quả Send Attachment: {attachment_send_res}")
    except Exception as e:
        print(f"Lỗi Upload Attachment: {e}")

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

    print("\n14. Test Get Notifications (Facebook Feature)...")
    try:
        notif_res = await get_notification_async(dataFB)
        print(f"Kết quả Get Notifications: Có {len(notif_res)} thông báo mới (Hiển thị 2 cái đầu): {notif_res[:2]}")
    except Exception as e:
        print(f"Lỗi Get Notifications: {e}")

    print("\n15. Test Change Bio (Facebook Feature)...")
    try:
        bio_res = await change_bio_async(dataFB, "Bot đang test fbchat-v2 bằng async/await 🚀", False)
        print(f"Kết quả Change Bio: {bio_res}")
    except Exception as e:
        print(f"Lỗi Change Bio: {e}")

    print("\n16. Test Get All Thread Data (Thread Feature)...")
    try:
        threads = await all_thread_data_async(dataFB)
        print(f"Kết quả All Thread Data: Đã lấy {len(threads)} nhóm (Hiển thị nhóm đầu tiên): {threads[0] if threads else 'Không có'}")
    except Exception as e:
        print(f"Lỗi All Thread Data: {e}")

    print("\n17. Test Change Name Thread (Thread Feature)...")
    try:
        name_res = await change_name_thread_async(dataFB, target_id, "FBChat v2 Async Test Group 🚀")
        print(f"Kết quả Change Name Thread: {name_res}")
    except Exception as e:
        print(f"Lỗi Change Name Thread: {e}")

    print("\n18. Test Create Post (Facebook Feature)...")
    try:
        post_res = await create_post_async(dataFB, "Bot FBChat-v2 test tạo bài viết! 🚀")
        print(f"Kết quả Create Post: {post_res}")
    except Exception as e:
        print(f"Lỗi Create Post: {e}")

    print("\n19. Test Blocking User (Facebook Feature)...")
    try:
        block_res = await blocking_async(dataFB, "4", "block") # Mark Zuckerberg
        print(f"Kết quả Blocking: {block_res}")
    except Exception as e:
        print(f"Lỗi Blocking: {e}")

    print("\n20. Test Professional Mode (Facebook Feature)...")
    try:
        pro_res = await professional_async(dataFB, "on")
        print(f"Kết quả Professional Mode: {pro_res}")
    except Exception as e:
        print(f"Lỗi Professional Mode: {e}")

    print("\n21. Test Marketplace Create Item (Facebook Feature)...")
    try:
        market_res = await marketplace_create_async(dataFB, "Bot Test Item", "Apple", 1000000, "VND", "Sản phẩm test từ fbchat-v2", ["test", "fbchat"], "Tools", [], {"latitude": 11.5614, "longitude": 108.9935})
        print(f"Kết quả Marketplace: {market_res}")
    except Exception as e:
        print(f"Lỗi Marketplace: {e}")

    print("\n22. Khởi động E2EE Listener & Gửi E2EE...")
    listener = listeningE2EEEvent(dataFB)
    listener.on_message(on_e2ee_message)
    listener_thread = threading.Thread(target=listener.connect_mqtt_blocking, daemon=True)
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
