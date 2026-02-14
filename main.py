from ncatbot.core import BotClient, GroupMessageEvent
from ncatbot.core.event import PrivateMessageEvent
from ncatbot.core.event.message_segment import File

bot = BotClient()


@bot.on_group_message()
async def on_message(event: GroupMessageEvent):
    print(event.raw_message)


@bot.on_group_message(filter = File)
async def on_message(event: GroupMessageEvent):
    print(event.raw_message)


@bot.on_private_message()
async def on_private_message(event: PrivateMessageEvent):
    print("收到私聊消息")


bot.run_frontend()

if __name__ == "__main__":
    pass
