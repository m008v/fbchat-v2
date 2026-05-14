import requests, json, random
from _core._utils import formAll, mainRequests, generate_client_id

# =====================================================================
# Messenger Notes (the temporary status-like notes shown in Messenger)
# Converted from ws3-fca/src/deltas/apis/messaging/notes.js
# =====================================================================

PRIVACY_ALIASES = {
     "EVERYONE": "FRIENDS",  # Messenger Notes hiện trả/nhận visibility FRIENDS
     "PUBLIC": "FRIENDS",
}
GRAPHQL_TIMEOUT = (10, 45)  # (connect timeout, read timeout) tính bằng giây
GRAPHQL_RETRIES = 2


def _normalize_privacy(privacy):
     return PRIVACY_ALIASES.get(str(privacy or "FRIENDS").upper(), str(privacy or "FRIENDS").upper())


def _error_response(resData):
     error = (resData.get("errors") or [{}])[0]
     return {
          "error": 1,
          "messages": error.get("message", str(error)),
          "details": error,
     }


def _request_error(message, exc=None, friendly_name=None, doc_id=None):
     error = {
          "message": message,
          "friendly_name": friendly_name,
          "doc_id": str(doc_id) if doc_id is not None else None,
     }
     if exc is not None:
          error["exception"] = str(exc)
     return {"errors": [error]}


def _post_graphql(dataFB, friendly_name, doc_id, variables, timeout=GRAPHQL_TIMEOUT, retries=GRAPHQL_RETRIES):
     """Gửi 1 GraphQL request và trả về JSON đã parse."""
     dataForm = formAll(dataFB, friendly_name, doc_id)
     dataForm["variables"] = json.dumps(variables)

     request_args = mainRequests(
          "https://www.facebook.com/api/graphql/",
          dataForm,
          dataFB["cookieFacebook"],
     )
     request_args["timeout"] = timeout

     last_error = None
     for attempt in range(retries + 1):
          try:
               response = requests.post(**request_args)
               response.raise_for_status()
               text = response.text
               if text.startswith("for (;;);"):
                    text = text.split("for (;;);", 1)[1]
               try:
                    return json.loads(text)
               except (ValueError, json.JSONDecodeError):
                    return {"errors": [{"message": "Invalid JSON response", "raw": text[:300]}]}
          except requests.Timeout as e:
               last_error = e
               if attempt < retries:
                    continue
               return _request_error(
                    f"Facebook GraphQL request timed out after {timeout[1]} seconds.",
                    e,
                    friendly_name,
                    doc_id,
               )
          except requests.RequestException as e:
               last_error = e
               if attempt < retries:
                    continue
               return _request_error("Facebook GraphQL request failed.", e, friendly_name, doc_id)

     return _request_error("Facebook GraphQL request failed after retry.", last_error, friendly_name, doc_id)


# ---------------------------------------------------------------------
# CHECK
# ---------------------------------------------------------------------
def checkNote(dataFB):
     """Kiểm tra note hiện tại của tài khoản đang đăng nhập."""
     variables = {"scale": 2}
     resData = _post_graphql(
          dataFB,
          "MWInboxTrayNoteCreationDialogQuery",
          30899655739648624,
          variables,
     )

     if resData.get("errors"):
          return _error_response(resData)

     try:
          currentNote = resData["data"]["viewer"]["actor"]["msgr_user_rich_status"]
     except (KeyError, TypeError):
          currentNote = None

     return {
          "success": 1,
          "messages": "Lấy note hiện tại thành công.",
          "data": currentNote,
     }


# ---------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------
def createNote(dataFB, text, privacy="FRIENDS"):
     """Tạo một note mới (mặc định tồn tại 24 giờ)."""
     variables = {
          "input": {
               "client_mutation_id": str(random.randint(0, 10)),
               "actor_id": str(dataFB["FacebookID"]),
               "description": text,
               "duration": 86400,  # 24 giờ
               "note_type": "TEXT_NOTE",
               "privacy": _normalize_privacy(privacy),
               "session_id": generate_client_id(),
          }
     }
     resData = _post_graphql(
          dataFB,
          "MWInboxTrayNoteCreationDialogCreationStepContentMutation",
          24060573783603122,
          variables,
     )

     if resData.get("errors"):
          return _error_response(resData)

     try:
          status = resData["data"]["xfb_rich_status_create"]["status"]
     except (KeyError, TypeError):
          status = None

     if status is None:
          return {
               "error": 1,
               "messages": "Could not find note status in the server response.",
               "raw": resData,
          }

     return {
          "success": 1,
          "messages": "Tạo note thành công.",
          "data": status,
     }


# ---------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------
def deleteNote(dataFB, noteID):
     """Xoá note theo ID."""
     variables = {
          "input": {
               "client_mutation_id": str(random.randint(0, 10)),
               "actor_id": str(dataFB["FacebookID"]),
               "rich_status_id": str(noteID),
          }
     }
     resData = _post_graphql(
          dataFB,
          "useMWInboxTrayDeleteNoteMutation",
          9532619970198958,
          variables,
     )

     if resData.get("errors"):
          return _error_response(resData)

     try:
          deletedStatus = resData["data"]["xfb_rich_status_delete"]
     except (KeyError, TypeError):
          deletedStatus = None

     if deletedStatus is None:
          return {
               "error": 1,
               "messages": "Could not find deletion status in the server response.",
               "raw": resData,
          }

     return {
          "success": 1,
          "messages": "Xoá note thành công.",
          "data": deletedStatus,
     }


# ---------------------------------------------------------------------
# RECREATE (delete + create)
# ---------------------------------------------------------------------
def recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS"):
     """Xoá note cũ rồi tạo note mới."""
     deleted = deleteNote(dataFB, oldNoteID)
     if deleted.get("error"):
          return deleted

     created = createNote(dataFB, newText, privacy=privacy)
     if created.get("error"):
          return created

     return {
          "success": 1,
          "messages": "Tạo lại note thành công.",
          "data": {
               "deleted": deleted.get("data"),
               "created": created.get("data"),
          },
     }


# ---------------------------------------------------------------------
# Default entry point (theo style fbchat-v2): func(dataFB, action, ...)
# ---------------------------------------------------------------------
def func(dataFB, action="check", **kwargs):
     """
     Args:
          dataFB: dict trả về từ _core._session.dataGetHome(setCookies)
          action: "check" | "create" | "delete" | "recreate"
          kwargs:
               - create:   text, privacy="FRIENDS"
               - delete:   noteID
               - recreate: oldNoteID, newText, privacy="FRIENDS"
     """
     action = (action or "check").lower()
     if action == "check":
          return checkNote(dataFB)
     if action == "create":
          return createNote(dataFB, kwargs["text"], privacy=kwargs.get("privacy", "FRIENDS"))
     if action == "delete":
          return deleteNote(dataFB, kwargs["noteID"])
     if action == "recreate":
          return recreateNote(
               dataFB,
               kwargs["oldNoteID"],
               kwargs["newText"],
               privacy=kwargs.get("privacy", "FRIENDS"),
          )
     return {"error": 1, "messages": f"Unknown action: {action}"}


""" Hướng dẫn sử dụng (Tutorial)

* Dữ liệu yêu cầu (args):

     - dataFB: lấy từ _core._session.dataGetHome(setCookies)
     - action: "check" / "create" / "delete" / "recreate"
     - text / privacy / noteID / oldNoteID / newText: tuỳ theo action

* Ví dụ:

     from _core._session import dataGetHome
     from _messaging import _createNotes

     dataFB = dataGetHome("<cookie Facebook>")
     _createNotes.checkNote(dataFB)
     _createNotes.createNote(dataFB, "Hello world", privacy="FRIENDS")
     _createNotes.deleteNote(dataFB, "<note_id>")
     _createNotes.recreateNote(dataFB, "<old_note_id>", "New note text")

* Kết quả trả về:
     - { "success": 1, "messages": "...", "data": {...} } khi thành công
     - { "error": 1, "messages": "..." } khi thất bại

* Thông tin tác giả:
     ✓ Convert from ws3-fca (notes.js by @ChoruOfficial) -> fbchat-v2 style
     ✓ Tôn trọng tác giả ❤️
"""
