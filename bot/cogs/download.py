import discord
from discord.ext import commands


class LocalPathCheck:
    pass


class Convert:
    pass


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Download(bot))