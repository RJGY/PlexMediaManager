import discord
import logging
import os

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class MyClient(discord.Client):
    async def on_ready(self):
        logging.debug('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        logging.debug('Message from {0.author}: {0.content}'.format(message))

client = MyClient()
client.run(os.environ['DISCORD_TOKEN'])