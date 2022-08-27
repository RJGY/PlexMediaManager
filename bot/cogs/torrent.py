import discord
from discord.ext import commands


class Torrenter:
    def __init__(self):
        pass

    def download_torrent(self, torrent_url):
        pass



class Torrent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="torrent")
    async def download_command(self, ctx, platform: str, search_term: str):
        """Torrents a video from selected platform."""
        await ctx.send(f"{platform}, {search_term}")


def setup(bot):
    bot.add_cog(Torrent(bot))