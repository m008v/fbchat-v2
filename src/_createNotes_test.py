"""
Test script cho `_messaging/_createNotes`
=========================================

Cách chạy:
     1) Tạo file `config.json` trong cùng thư mục `src/` (hoặc dùng sẵn nếu đã có):
          {
               "cookies": "c_user=...; xs=...; fr=...; datr=...;"
          }
     2) Chạy:
          python _createNotes_test.py
          python _createNotes_test.py check
          python _createNotes_test.py create "Hello from fbchat-v2"
          python _createNotes_test.py create "Hello friends" FRIENDS
          python _createNotes_test.py delete <noteID>
          python _createNotes_test.py recreate <oldNoteID> "New text"
          python _createNotes_test.py full         # check -> create -> check -> delete

Mặc định không truyền tham số sẽ chạy chế độ `full`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
     sys.path.insert(0, str(HERE))

from _core._session import dataGetHome
from _messaging import _createNotes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
CONFIG_PATH = HERE / "config.json"


def load_cookie() -> str:
     if not CONFIG_PATH.exists():
          print(f"[!] Không tìm thấy {CONFIG_PATH}")
          print('    Tạo file config.json với nội dung: {"cookies": "c_user=...; xs=...;"}')
          sys.exit(1)
     try:
          cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
     except Exception as e:
          print(f"[!] Đọc config.json lỗi: {e}")
          sys.exit(1)
     cookie = (cfg.get("cookies") or cfg.get("cookie") or "").strip()
     if not cookie:
          print("[!] Thiếu trường 'cookies' trong config.json")
          sys.exit(1)
     return cookie


def pretty(obj) -> str:
     try:
          return json.dumps(obj, ensure_ascii=False, indent=2)
     except Exception:
          return str(obj)


def print_section(title: str) -> None:
     bar = "=" * 60
     print(f"\n{bar}\n{title}\n{bar}")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_check(dataFB):
     print_section("CHECK NOTE")
     res = _createNotes.checkNote(dataFB)
     print(pretty(res))
     return res


def action_create(dataFB, text: str, privacy: str = "FRIENDS"):
     print_section(f"CREATE NOTE  text={text!r}  privacy={privacy}")
     res = _createNotes.createNote(dataFB, text, privacy=privacy)
     print(pretty(res))
     return res


def action_delete(dataFB, note_id: str):
     print_section(f"DELETE NOTE  id={note_id}")
     res = _createNotes.deleteNote(dataFB, note_id)
     print(pretty(res))
     return res


def action_recreate(dataFB, old_id: str, new_text: str):
     print_section(f"RECREATE NOTE  old={old_id}  newText={new_text!r}")
     res = _createNotes.recreateNote(dataFB, old_id, new_text)
     print(pretty(res))
     return res


def action_full(dataFB):
     """Kịch bản end-to-end: check -> create -> check -> delete -> check."""
     action_check(dataFB)

     created = action_create(dataFB, f"fbchat-v2 test @ {int(time.time())}")
     if created.get("error"):
          print("[!] Create thất bại, dừng kịch bản full.")
          return

     time.sleep(1)
     after_create = action_check(dataFB)

     # cố trích noteID từ kết quả check (vị trí trường có thể khác nhau)
     data = after_create.get("data") or {}
     note_id = (
          data.get("id")
          or data.get("rich_status_id")
          or (data.get("note") or {}).get("id")
     )
     # fallback: thử lấy id từ chính kết quả create
     if not note_id:
          created_data = created.get("data") or {}
          note_id = (
               created_data.get("id")
               or (created_data.get("rich_status") or {}).get("id")
          )

     if not note_id:
          print("[!] Không xác định được noteID để xoá. Bỏ qua bước delete.")
          print("    Dump created:", pretty(created))
          return

     time.sleep(1)
     action_delete(dataFB, note_id)

     time.sleep(1)
     action_check(dataFB)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
     args = sys.argv[1:]
     command = (args[0] if args else "full").lower()

     cookie = load_cookie()
     print("[*] Đang lấy fb_dtsg / jazoest từ cookie...")
     try:
          dataFB = dataGetHome(cookie)
     except requests.RequestException as e:
          print(f"[!] Lỗi mạng khi lấy data home Facebook: {e}")
          sys.exit(2)
     fbid = dataFB.get("FacebookID")
     if not fbid or "Unable to retrieve" in str(dataFB.get("fb_dtsg", "")):
          print("[!] Cookie có vẻ không hợp lệ.")
          print(pretty(dataFB))
          sys.exit(2)
     print(f"[+] OK. FacebookID = {fbid}")

     if command == "check":
          action_check(dataFB)
     elif command == "create":
          if len(args) < 2:
               print("Usage: python _createNotes_test.py create <text> [privacy]")
               sys.exit(1)
          text = args[1]
          privacy = args[2] if len(args) > 2 else "FRIENDS"
          action_create(dataFB, text, privacy)
     elif command == "delete":
          if len(args) < 2:
               print("Usage: python _createNotes_test.py delete <noteID>")
               sys.exit(1)
          action_delete(dataFB, args[1])
     elif command == "recreate":
          if len(args) < 3:
               print("Usage: python _createNotes_test.py recreate <oldNoteID> <newText>")
               sys.exit(1)
          action_recreate(dataFB, args[1], args[2])
     elif command in ("full", "all"):
          action_full(dataFB)
     else:
          print(f"Unknown command: {command}")
          print("Available: check | create | delete | recreate | full")
          sys.exit(1)


if __name__ == "__main__":
     main()
