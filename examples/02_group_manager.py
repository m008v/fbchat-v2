"""Quản lý một nhóm test; poll trong RAM bằng tin nhắn, không phải poll native."""

from dataclasses import dataclass, field
import json

import httpx
from fbchat_v2 import SendAPI
from fbchat_v2._features._thread import _all_thread_data, _changeNickname

from _common import ConfigurationError, Message, required_env, run, standard_messages


@dataclass
class Poll:
    question: str
    options: list[str]
    votes: dict[str, int] = field(default_factory=dict)

    @classmethod
    def parse(cls, argument: str) -> "Poll":
        parts = [part.strip() for part in argument.split("|")]
        if (
            not 3 <= len(parts) <= 7
            or not 1 <= len(parts[0]) <= 200
            or any(not 1 <= len(option) <= 80 for option in parts[1:])
            or len(set(parts[1:])) != len(parts[1:])
        ):
            raise ValueError("Dùng /poll Câu hỏi | Lựa chọn 1 | Lựa chọn 2 (tối đa 6).")
        return cls(parts[0], parts[1:])

    def vote(self, sender: str, number: str) -> str:
        if not number.isascii() or not number.isdecimal():
            return "Gửi số thứ tự của lựa chọn để bỏ phiếu."
        choice = int(number)
        if not 1 <= choice <= len(self.options):
            return "Số lựa chọn không hợp lệ."
        if sender not in self.votes and len(self.votes) >= 1000:
            return "Poll đã đủ 1000 người bỏ phiếu."
        self.votes[sender] = choice
        return "Đã ghi nhận phiếu; gửi số khác nếu muốn đổi lựa chọn."

    def results(self) -> str:
        lines = [self.question]
        for index, option in enumerate(self.options, 1):
            count = sum(choice == index for choice in self.votes.values())
            lines.append(f"{index}. {option}: {count} phiếu")
        return "\n".join(lines)


async def find_members(
    session: dict[str, object], thread_id: str, query: str, client: httpx.AsyncClient
) -> str:
    threads = await _all_thread_data.func(session, client=client)
    payload = threads.get("dataGet")
    if not isinstance(payload, str):
        return "Không tải được danh sách nhóm."
    exported = await _all_thread_data.features(
        payload, thread_id, "exportMemberListToJson"
    )
    if not isinstance(exported, list):
        return "Không tìm thấy nhóm trong danh sách đã tải (tối đa 50 cuộc trò chuyện)."
    matches = []
    for entry in exported:
        for user_id, member in json.loads(entry).items():
            name = str(member.get("nameFB") or "")
            if query.casefold() in name.casefold():
                matches.append(f"{name}: {user_id}")
    return "\n".join(matches[:20]) or "Không có thành viên khớp tên."


class GroupManager:
    def __init__(self, admin_id: str) -> None:
        self.admin_id = admin_id
        self.poll: Poll | None = None

    async def handle(
        self, message: Message, session: dict[str, object], client: httpx.AsyncClient
    ) -> str | None:
        text = message["body"].strip()
        command, _, argument = text.partition(" ")
        argument = argument.strip()
        if text.isascii() and text.isdecimal():
            return self.poll.vote(message["userID"], text) if self.poll else None
        if command == "/results":
            return self.poll.results() if self.poll else "Chưa có poll đang mở."
        if command not in {"/nick", "/members", "/poll", "/close"}:
            return None
        if message["userID"] != self.admin_id:
            return "Chỉ admin cấu hình trong FB_ADMIN_ID mới dùng được lệnh này."
        if command == "/members":
            return await find_members(session, message["replyToID"], argument, client)
        if command == "/nick":
            user_id, _, nickname = argument.partition(" ")
            if not user_id.isdecimal() or not 1 <= len(nickname.strip()) <= 80:
                return "Dùng /nick ID_THÀNH_VIÊN Biệt danh mới (tối đa 80 ký tự)."
            result = await _changeNickname.func(
                session, message["replyToID"], user_id, nickname.strip(), client=client
            )
            return (
                "Đã đổi biệt danh."
                if result.get("status") == "success"
                else "Không đổi được biệt danh."
            )
        if command == "/close":
            if self.poll is None:
                return "Chưa có poll đang mở."
            poll_result = self.poll.results()
            self.poll = None
            return poll_result
        if self.poll is not None:
            return "Đã có poll đang mở; dùng /close trước khi tạo poll khác."
        try:
            self.poll = Poll.parse(argument)
        except ValueError as error:
            return str(error)
        return (
            self.poll.results() + "\nTrả lời bằng số để bỏ phiếu; /results xem kết quả."
        )


async def main() -> None:
    admin_id = required_env("FB_ADMIN_ID")
    if not admin_id.isdecimal():
        raise ConfigurationError("FB_ADMIN_ID phải là ID người dùng dạng số.")
    manager = GroupManager(admin_id)
    async with standard_messages() as (session, messages):
        async with httpx.AsyncClient(timeout=30) as client:
            async for message in messages:
                try:
                    reply = await manager.handle(message, session, client)
                    if reply:
                        await SendAPI().send(
                            session, reply, message["replyToID"], client=client
                        )
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    print(
                        "Lệnh thất bại; không in nội dung hoặc lỗi provider, không tự gửi lại."
                    )


if __name__ == "__main__":
    run(main())
