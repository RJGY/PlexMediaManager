import discord
from discord.ext import commands
import datetime as dt
import requests
import os
from dotenv import load_dotenv
import json

PLAYERS = ['Janice', 'mítsu', 'Naafiramas', '2 Balls', 'TeemooBot145', 'zevnik', 'Eldenbel', 'EEEMOO', 'AssassinAbuser69', '3213913898943']

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
        print(f'{self.name} {self.tier} {self.rank} {self.lp} {self.wins} {self.losses} {self.winrate}')
    

class LeagueAPI:
    def __init__(self, api_key):
        self.api_key = f'api_key={api_key}'
        self.players = []
        self.player_ids = []
        
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
        
    def get_players_ids(self):
        for player in PLAYERS:
            req = requests.get(f'{BASE_LEAGUE_ENDPOINT}/summoner/v4/summoners/by-name/{player}?{self.api_key}')
            print(req.text)
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
        self.api = LeagueAPI(AUTH_TOKEN)
        self.api.get_players_ids()
        
    @commands.command(name = "refresh", help = "Refreshes the list of players in the league channel")
    @commands.cooldown(1, 120, commands.BucketType.guild)
    async def refresh_command(self, ctx):
        await ctx.send("Refreshing...")
        self.api.get_players_rank()
        self.api.convert_players_ranks()
        self.api.sort_players()
        self.api.convert_back_players_ranks()
        embed = discord.Embed(
            title="Leaderboard",
            description=f"Showing how boosted kaia is :3", 
            colour=ctx.author.colour,
            timestamp=dt.datetime.now()
        )
        
        embed.set_author(name="League of Legends Rank Leaderboard")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        for i in range(len(self.api.players)):
            embed.add_field(name=f'{i+1}. {self.api.players[i].name}', value=f'{self.api.players[i].tier} {self.api.players[i].rank} {self.api.players[i].lp} LP\n {self.api.players[i].wins}W {self.api.players[i].losses}L Winrate {self.api.players[i].winrate}%', inline=False)
        await ctx.send(embed=embed)
        self.api.flush_players()
    
    
    @refresh_command.error
    async def refresh_command_error(self, ctx, exc):
        if isinstance(exc, discord.ext.commands.errors.CommandOnCooldown):
            await ctx.send("Command on cooldown. Please wait " + str(exc.retry_after) + " seconds.")
        
        

async def setup(bot):
    await bot.add_cog(League(bot))
    
    
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