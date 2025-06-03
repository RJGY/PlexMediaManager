import discord
from discord.ext import commands, tasks
import datetime as dt
import requests
import os
from dotenv import load_dotenv
import json
import logging

PLAYERS = ['Janice', 'mítsu', 'Naafiramas', '2 Balls', 'TeemooBot145', 'zevnik', 'Eldenbel', 'EEEMOO', 'AssassinAbuser69', 'lIIlIIIlIIIlIIIl']

TIERS = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']

RANKS = ['IV', 'III', 'II', 'I']

RANKED_SOLO = 'RANKED_SOLO_5x5'

load_dotenv()

AUTH_TOKEN = os.environ.get('RIOT_AUTH_TOKEN')

BASE_LEAGUE_ENDPOINT = 'https://oc1.api.riotgames.com/lol'

class Summoner:
    def __init__(self, name, tier, rank, lp, wins, losses):
        self.name = name
        self.tier = tier
        self.rank = rank
        self.lp = lp
        self.wins = wins
        self.losses = losses
        self.winrate = int(wins / (wins + losses) * 100)
        logging.basicConfig(level=logging.DEBUG,
                            format="%(levelname)s %(asctime)s: %(name)s: %(message)s (Line: %(lineno)d) [%(filename)s]",
                            datefmt="%d/%m/%Y %I:%M:%S %p")
        logging.info(f'{self.name} {self.tier} {self.rank} {self.lp} {self.wins} {self.losses} {self.winrate}')
    

class LeagueAPI:
    def __init__(self, api_key):
        self.api_key = f'api_key={api_key}'
        self.players = []
        self.player_ids = []
        if not self.check_api_key():
            logging.error("Invalid Riot API key. Please check your .env file.")
        
    def convert_rank(self, rank):
        for i in range(len(RANKS)):
            if rank == RANKS[i]:
                return i
        return -1
    
    def convert_tier(self, tier):
        for i in range(len(TIERS)):
            if tier == TIERS[i]:
                return i
        return -1
        
    def check_api_key(self):
        req = requests.get(f'{BASE_LEAGUE_ENDPOINT}/summoner/v4/summoners/by-name/Janice?{self.api_key}')
        if req.status_code == 200:
            return True
        return False 
    
    def get_players_ids(self):
        for player in PLAYERS:
            req = requests.get(f'{BASE_LEAGUE_ENDPOINT}/summoner/v4/summoners/by-name/{player}?{self.api_key}')
            json_data = json.loads(req.text)
            self.player_ids.append(json_data['id'])
    
    def get_players_rank(self):
        for player_id in self.player_ids:
            req = requests.get(f'{BASE_LEAGUE_ENDPOINT}/league/v4/entries/by-summoner/{player_id}?{self.api_key}')
            json_data = json.loads(req.text)
            for queue in json_data:
                if queue['queueType'] == RANKED_SOLO:
                    self.players.append(Summoner(queue['summonerName'], queue['tier'], queue['rank'], queue['leaguePoints'], queue['wins'], queue['losses']))
    
    def convert_players_ranks(self):
        for player in self.players:
            player.rank = self.convert_rank(player.rank)
            player.tier = self.convert_tier(player.tier)
            
    def convert_back_players_ranks(self):
        for player in self.players:
            player.rank = RANKS[player.rank]
            player.tier = TIERS[player.tier]
            
    def sort_players(self):
        for i in range(len(self.players)):
            for j in range(len(self.players)):
                if self.players[i].tier > self.players[j].tier:
                    self.players[i], self.players[j] = self.players[j], self.players[i]
                elif self.players[i].tier == self.players[j].tier:
                    if self.players[i].rank > self.players[j].rank:
                        self.players[i], self.players[j] = self.players[j], self.players[i]
                    elif self.players[i].rank == self.players[j].rank:
                        if self.players[i].lp > self.players[j].lp:
                            self.players[i], self.players[j] = self.players[j], self.players[i]
                            
    def flush_players(self):
        self.players = []
    

class League(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.toggle_leaderboard = False
        self.leaderboard = None
        self.leaderboard_channel = None
        self.leaderboard_member = None
        self.api = LeagueAPI(AUTH_TOKEN)
        self.api.get_players_ids()
        
    @commands.command(name = "ladder", help = "Manually retrieves the ranked ladder data.")
    @commands.cooldown(1, 120, commands.BucketType.guild)
    async def manual_leaderboard_command(self, ctx):
        await ctx.send("Refreshing...")
        self.api.flush_players()
        self.api.get_players_rank()
        self.api.convert_players_ranks()
        self.api.sort_players()
        self.api.convert_back_players_ranks()
        embed = discord.Embed(
            title="Leaderboard",
            description=f"Showing how boosted kaia is :3", 
            colour=discord.Colour.green(),
            timestamp=dt.datetime.now()
        )
        
        embed.set_author(name="League of Legends Rank Leaderboard")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        for i in range(len(self.api.players)):
            embed.add_field(name=f'{i+1}. {self.api.players[i].name}', value=f'{self.api.players[i].tier} {self.api.players[i].rank} {self.api.players[i].lp} LP\n {self.api.players[i].wins}W {self.api.players[i].losses}L Winrate {self.api.players[i].winrate}%', inline=False)
        await ctx.send(embed=embed)
        
    @manual_leaderboard_command.error
    async def manual_leaderboard_command_error(self, ctx, exc):
        if isinstance(exc, discord.ext.commands.errors.CommandOnCooldown):
            await ctx.send("Command on cooldown. Please wait " + str(exc.retry_after) + " seconds.")
        
    @commands.command(name = "leaderboard", help = "Shows the current leaderboard")
    async def toggle_leaderboard_command(self, ctx):
        
        """completely unneccessary just here for fun lmao"""
        if ctx.author.name != 'rjgy':
            await ctx.send("You are not him. You cannot use this command.")
            return
        else:
            await ctx.send("You are him. You can use this command.")
        """completely unneccessary just here for fun lmao"""
        
        if self.leaderboard and self.toggle_leaderboard:
            self.toggle_leaderboard = False
            self.leaderboard = None
            self.leaderboard_channel = None
            await ctx.send("Leaderboard update disabled.")
            self.auto_leaderboard.cancel()
            return
            
        await ctx.send("Loading...")
        self.api.flush_players()
        self.api.get_players_rank()
        self.api.convert_players_ranks()
        self.api.sort_players()
        self.api.convert_back_players_ranks()
        embed = discord.Embed(
            title="Leaderboard",
            description=f"Showing how boosted kaia is :3", 
            colour=discord.Colour.green(),
            timestamp=dt.datetime.now()
        )
        
        embed.set_author(name="League of Legends Rank Leaderboard")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        for i in range(len(self.api.players)):
            embed.add_field(name=f'{i+1}. {self.api.players[i].name}', value=f'{self.api.players[i].tier} {self.api.players[i].rank} {self.api.players[i].lp} LP\n {self.api.players[i].wins}W {self.api.players[i].losses}L Winrate {self.api.players[i].winrate}%', inline=False)
        self.leaderboard = await ctx.send(embed=embed)
        self.leaderboard_channel = ctx.channel
        self.toggle_leaderboard = True
        self.leaderboard_member = ctx.author
        self.auto_leaderboard.start()
        
    @tasks.loop(hours=1)
    async def auto_leaderboard(self):
        if self.toggle_leaderboard:
            refresh_message = await self.leaderboard_channel.send("Refreshing...")
            self.api.flush_players()
            self.api.get_players_rank()
            self.api.convert_players_ranks()
            self.api.sort_players()
            self.api.convert_back_players_ranks()
            embed = discord.Embed(
                title="Leaderboard",
                description=f"Showing how boosted kaia is :3", 
                colour=discord.Colour.green(),
                timestamp=dt.datetime.now()
            )
            
            embed.set_author(name="League of Legends Rank Leaderboard")
            embed.set_footer(text=f"Requested by {self.leaderboard_member.display_name}", icon_url=self.leaderboard_member.display_avatar.url)
            for i in range(len(self.api.players)):
                embed.add_field(name=f'{i+1}. {self.api.players[i].name}', value=f'{self.api.players[i].tier} {self.api.players[i].rank} {self.api.players[i].lp} LP\n {self.api.players[i].wins}W {self.api.players[i].losses}L Winrate {self.api.players[i].winrate}%', inline=False)
            await self.leaderboard.edit(embed=embed)
            await refresh_message.delete()
    
    @commands.command(name = "refresh", help = "Refreshes the automatic leaderboard.")
    @commands.cooldown(1, 120, commands.BucketType.guild)
    async def manual_refresh(self, ctx):
        if self.toggle_leaderboard:
            refresh_message = await self.leaderboard_channel.send("Refreshing...")
            self.api.flush_players()
            self.api.get_players_rank()
            self.api.convert_players_ranks()
            self.api.sort_players()
            self.api.convert_back_players_ranks()
            embed = discord.Embed(
                title="Leaderboard",
                description=f"Showing how boosted kaia is :3", 
                colour=discord.Colour.green(),
                timestamp=dt.datetime.now()
            )
            
            embed.set_author(name="League of Legends Rank Leaderboard")
            embed.set_footer(text=f"Requested by {self.leaderboard_member.display_name}", icon_url=self.leaderboard_member.display_avatar.url)
            for i in range(len(self.api.players)):
                embed.add_field(name=f'{i+1}. {self.api.players[i].name}', value=f'{self.api.players[i].tier} {self.api.players[i].rank} {self.api.players[i].lp} LP\n {self.api.players[i].wins}W {self.api.players[i].losses}L Winrate {self.api.players[i].winrate}%', inline=False)
            await self.leaderboard.edit(embed=embed)
            await refresh_message.delete()
            await ctx.message.delete()
            
        
    @manual_refresh.error
    async def manual_refresh_error(self, ctx, exc):
        if isinstance(exc, discord.ext.commands.errors.CommandOnCooldown):
            await ctx.send("Command on cooldown. Please wait " + str(exc.retry_after) + " seconds.")
            
    @commands.command(name="help_league")
    async def help_league_command(self, ctx: commands.Context):
        """Displays help information for all league commands."""
        embed = discord.Embed(
            title="League Commands",
            description="Here's a list of available league commands:",
            color=discord.Color.blue()  # You can choose any color
        )

        for command in self.get_commands():
            if command.name == "help_league":  # Don't include the help command itself
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
    await bot.add_cog(League(bot))
    
""" Tests """
    
def test():
    api = LeagueAPI('')
    api.get_players_ids()
    api.get_players_rank()
    api.convert_players_ranks()
    api.sort_players()
    api.convert_back_players_ranks()
    for player in api.players:
        print(f'{player.name} {player.tier} {player.rank} {player.lp}')
    
    
if __name__ == "__main__":
    test()