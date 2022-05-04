import discord
import os
from dotenv import load_dotenv

load_dotenv()

discord_symbol = os.getenv('SYMBOL')

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))
        if message.author.id == self.user.id:
            return

        if message.content.startswith(discord_symbol + 'hello'):
            await message.reply('Hello!', mention_author=True)


client = MyClient()
client.run(os.getenv('DISCORD_TOKEN'))