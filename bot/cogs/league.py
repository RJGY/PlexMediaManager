import discord
from discord import app_commands # Added
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
        
    @app_commands.command(name="show_ladder", description="Manually retrieves and shows the ranked ladder data.")
    @app_commands.checks.cooldown(1, 120, key=lambda i: i.guild_id)
    async def show_ladder_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Send an initial followup after deferring, as API calls might be slow.
        await interaction.followup.send("Refreshing ladder data, please wait...")

        # These Riot API calls can be blocking. Consider running them in a thread.
        # For now, let's assume they are quick enough or this will be addressed later.
        self.api.flush_players()
        self.api.get_players_rank()
        self.api.convert_players_ranks()
        self.api.sort_players()
        self.api.convert_back_players_ranks()

        embed = discord.Embed(
            title="Ranked Leaderboard", # More generic title
            description="Current ranked standings of registered players.", # More descriptive
            colour=discord.Colour.blue(), # Standard color
            timestamp=dt.datetime.now()
        )
        
        embed.set_author(name="League of Legends OCE Ladder") # More specific author
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )

        if not self.api.players:
            embed.add_field(name="No Players Found", value="Could not retrieve player data or no players are ranked.", inline=False)
        else:
            for i, player in enumerate(self.api.players):
                embed.add_field(
                    name=f'{i+1}. {player.name}',
                    value=f'{player.tier} {player.rank} - {player.lp} LP\nWins: {player.wins} | Losses: {player.losses} (WR: {player.winrate}%)',
                    inline=False
                )
        
        # Edit the initial followup message with the embed
        await interaction.edit_original_response(content=None, embed=embed)
        
    # @manual_leaderboard_command.error # This line was correctly commented out/removed by previous step
    # Removed manual_leaderboard_command_error (will be handled by cog_app_command_error)
        
    @app_commands.command(name="auto_leaderboard_toggle", description="Toggles the automatic hourly leaderboard update.")
    async def auto_leaderboard_toggle_command(self, interaction: discord.Interaction):
        # Owner check - consider using app_commands.checks.is_owner() or a specific role/ID check for production
        if interaction.user.name != 'rjgy': # Simple check for now
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer() # Defer as it might fetch data

        if self.leaderboard and self.toggle_leaderboard:
            self.toggle_leaderboard = False
            if self.leaderboard: # Ensure leaderboard message exists
                 try:
                    await self.leaderboard.edit(content="Automatic leaderboard updates disabled.", embed=None, view=None)
                 except discord.NotFound:
                    logging.warning("Leaderboard message not found when trying to disable.")
                 except discord.HTTPException as e:
                    logging.error(f"Failed to edit leaderboard message: {e}")
            self.leaderboard = None
            self.leaderboard_channel = None
            self.leaderboard_member = None # Clear member info
            self.auto_leaderboard.cancel()
            await interaction.followup.send("Automatic leaderboard updates disabled.")
            return
            
        await interaction.followup.send("Loading initial leaderboard data...")
        # These API calls can be blocking. Consider asyncio.to_thread for production.
        self.api.flush_players()
        self.api.get_players_rank()
        self.api.convert_players_ranks()
        self.api.sort_players()
        self.api.convert_back_players_ranks()

        embed = discord.Embed(
            title="Ranked Leaderboard",
            description="Current ranked standings. Will update hourly.",
            colour=discord.Colour.green(), # Keep original color for auto-leaderboard
            timestamp=dt.datetime.now()
        )
        
        embed.set_author(name="League of Legends OCE Ladder")
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )

        if not self.api.players:
            embed.add_field(name="No Players Found", value="Could not retrieve player data or no players are ranked.", inline=False)
        else:
            for i, player in enumerate(self.api.players):
                embed.add_field(
                    name=f'{i+1}. {player.name}',
                    value=f'{player.tier} {player.rank} - {player.lp} LP\nWins: {player.wins} | Losses: {player.losses} (WR: {player.winrate}%)',
                    inline=False
                )

        # Send the new leaderboard message
        # The initial message "Loading initial leaderboard data..." will be edited by this.
        # Or, if we want that message to persist and send a new one:
        # await interaction.edit_original_response(content="Leaderboard initialized.", embed=embed)
        # For now, let's assume we send a new message for the leaderboard itself if followup was used for "Loading..."

        # Correction: Since we used followup.send for "Loading...", we need another followup for the embed.
        # Or, edit the "Loading..." message. Let's edit.
        self.leaderboard = await interaction.edit_original_response(content=None, embed=embed)
        if not self.leaderboard: # If edit_original_response doesn't return the message (it should return None)
            # We might need to fetch the message if interaction.channel.last_message_id is reliable after edit_original_response
            # Or, send a new message using followup if edit doesn't give us the message object easily
             self.leaderboard = await interaction.followup.send(embed=embed) # Fallback to sending new if edit doesn't return it

        self.leaderboard_channel = interaction.channel
        self.toggle_leaderboard = True
        self.leaderboard_member = interaction.user # Store the user who initiated
        self.auto_leaderboard.start()
        # No need to send another "enabled" message if the embed is now visible.
        # The presence of the updating leaderboard is the indicator.
        
    @tasks.loop(hours=1)
    async def auto_leaderboard(self):
        if self.toggle_leaderboard and self.leaderboard_channel and self.leaderboard: # Added checks for channel and message
            refresh_message = None # Initialize to None
            try:
                refresh_message = await self.leaderboard_channel.send("Refreshing automatic leaderboard...")
                self.api.flush_players()
                # These API calls can be blocking. Consider asyncio.to_thread for production.
                self.api.get_players_rank()
                self.api.convert_players_ranks()
                self.api.sort_players()
                self.api.convert_back_players_ranks()

                embed = discord.Embed(
                    title="Ranked Leaderboard", # Consistent title
                    description="Current ranked standings. Updates hourly.", # Consistent description
                    colour=discord.Colour.green(), # Keep original color
                    timestamp=dt.datetime.now()
                )
                embed.set_author(name="League of Legends OCE Ladder") # Consistent author
                if self.leaderboard_member: # Ensure member is still set for footer
                    embed.set_footer(
                        text=f"Automatic hourly update. Initiated by {self.leaderboard_member.display_name}",
                        icon_url=self.leaderboard_member.display_avatar.url if self.leaderboard_member.display_avatar else None
                    )

                if not self.api.players:
                    embed.add_field(name="No Players Found", value="Could not retrieve player data or no players are ranked.", inline=False)
                else:
                    for i, player in enumerate(self.api.players):
                        embed.add_field(
                            name=f'{i+1}. {player.name}',
                            value=f'{player.tier} {player.rank} - {player.lp} LP\nWins: {player.wins} | Losses: {player.losses} (WR: {player.winrate}%)',
                            inline=False
                        )
                await self.leaderboard.edit(embed=embed)
            except discord.NotFound:
                logging.error("Failed to find leaderboard message or channel for auto-update. Disabling auto-leaderboard.")
                self.toggle_leaderboard = False # Disable if message/channel is gone
                self.auto_leaderboard.cancel()
            except discord.HTTPException as e:
                logging.error(f"HTTP error during auto-leaderboard update: {e}")
            except Exception as e: # Catch any other unexpected errors
                logging.error(f"Unexpected error during auto-leaderboard update: {e}", exc_info=True)
            finally:
                if refresh_message: # Ensure refresh_message was successfully created
                    try:
                        await refresh_message.delete()
                    except discord.HTTPException:
                        pass # Ignore if deleting the refresh message fails
    
    @app_commands.command(name="refresh_auto_leaderboard", description="Manually refreshes the automatic leaderboard if active.")
    @app_commands.checks.cooldown(1, 120, key=lambda i: i.guild_id)
    async def refresh_auto_leaderboard_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.toggle_leaderboard or not self.leaderboard or not self.leaderboard_channel:
            await interaction.followup.send("The automatic leaderboard is not currently active or not properly initialized.", ephemeral=True)
            return

        # Notify that refresh is starting (ephemeral followup to the deferral)
        await interaction.followup.send("Attempting to refresh the leaderboard...", ephemeral=True)

        # Perform the refresh logic (similar to the loop's body)
        try:
            # These API calls can be blocking. Consider asyncio.to_thread for production.
            self.api.flush_players()
            self.api.get_players_rank()
            self.api.convert_players_ranks()
            self.api.sort_players()
            self.api.convert_back_players_ranks()

            embed = discord.Embed(
                title="Ranked Leaderboard",
                description="Current ranked standings. (Manually Refreshed)",
                colour=discord.Colour.green(), # Keep original color
                timestamp=dt.datetime.now()
            )
            embed.set_author(name="League of Legends OCE Ladder")
            # Use the interaction user for "refreshed by"
            embed.set_footer(
                text=f"Manually refreshed by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
            )

            if not self.api.players:
                embed.add_field(name="No Players Found", value="Could not retrieve player data or no players are ranked.", inline=False)
            else:
                for i, player in enumerate(self.api.players):
                    embed.add_field(
                        name=f'{i+1}. {player.name}',
                        value=f'{player.tier} {player.rank} - {player.lp} LP\nWins: {player.wins} | Losses: {player.losses} (WR: {player.winrate}%)',
                        inline=False
                    )
            
            await self.leaderboard.edit(embed=embed)
            # Edit the ephemeral followup to confirm success
            # Cannot edit the same ephemeral followup twice. Send a new one.
            # await interaction.edit_original_response(content="Leaderboard refreshed successfully.")
            # Instead, since the defer was ephemeral, this new followup will also be by default if content is simple string
            await interaction.followup.send("Leaderboard refreshed successfully.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("Error: Leaderboard message not found. It might have been deleted. Please toggle it off and on again.", ephemeral=True)
            self.toggle_leaderboard = False # Disable if message is gone
            self.auto_leaderboard.cancel()
        except Exception as e:
            logging.error(f"Error during manual leaderboard refresh: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred during refresh: {e}", ephemeral=True)
            
        
    # Removed manual_refresh_error (will be handled by cog_app_command_error)
            
    # Removed help_league_command

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for app commands in this cog."""
        logging.error(f"Error in League cog, command '{interaction.command.name if interaction.command else 'Unknown'}': {error}", exc_info=error)
        ephemeral = True
        message = f"An unexpected error occurred: {error}"

        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds."
        # Add more specific error handling here if needed for other custom errors from this cog
        # For example:
        # elif isinstance(error.original, YourCustomErrorInLeagueCog):
        #     message = str(error.original)

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            try:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            except discord.errors.InteractionResponded: # Should not happen if is_done() is false, but as a safeguard
                await interaction.followup.send(message, ephemeral=ephemeral)
            except Exception as e:
                logging.error(f"Failed to send error message for League cog: {e}")
            
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