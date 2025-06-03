import discord
from discord.ext import commands


class Torrenter:
    def __init__(self):
        pass

    def download_torrent(self, torrent_url):
        pass


class WebScraper:
    def __init__(self):
        pass

    def get_torrent_url(self, search_query, platform):
        """Gets torrent magnet link from a search query"""
        
        pass


class Torrent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="torrent")
    async def download_command(self, ctx, platform: str, search_term: str):
        """Torrents a video from selected platform."""
        await ctx.send(f"{platform}, {search_term}")

    @commands.command(name="help_torrent")
    async def help_torrent_command(self, ctx: commands.Context):
        """Displays help information for all torrent commands."""
        embed = discord.Embed(
            title="Torrent Commands",
            description="Here's a list of available torrent commands:",
            color=discord.Color.blue()  # You can choose any color
        )

        for command in self.get_commands():
            if command.name == "help_torrent":  # Don't include the help command itself
                continue

            name = command.name
            # params = [param for param in command.params if param not in ("self", "ctx")] # Not strictly needed if using signature

            # Try to generate a more user-friendly signature
            if command.signature:
                usage = f"`{ctx.prefix}{name} {command.signature}`"
            else:
                usage = f"`{ctx.prefix}{name}`" # Fallback if signature is empty

            # Use the command's short doc or the full docstring
            description = command.short_doc or command.help or "No description available."

            embed.add_field(name=name.capitalize(), value=f"{description}\n**Usage:** {usage}", inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Torrent(bot))