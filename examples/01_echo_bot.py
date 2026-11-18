from fbchat_v2 import SendAPI

from _common import run, standard_messages


async def main() -> None:
    async with standard_messages() as (session, messages):
        async for message in messages:
            await SendAPI().send(session, message["body"], message["replyToID"])


if __name__ == "__main__":
    run(main())
