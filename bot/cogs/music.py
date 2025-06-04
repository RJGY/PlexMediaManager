import asyncio
import datetime as dt
import enum
from itertools import repeat

import typing as t
import random
import re

import discord
import wavelink
from discord import app_commands # Added
from discord.ext import commands
from discord.ext.commands import Bot

# Constants

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}

class RepeatMode(enum.Enum):
    NONE = 0
    SONG = 1
    ALL = 2


# Errors

class IncorrectArgumentType(commands.CommandError):
    pass


class MissingArgument(commands.CommandError):
    pass


class InvalidRepeatMode(commands.CommandError):
    pass


class PlayerIsAlreadyResumed(commands.CommandError):
    pass


class AlreadyConnectedToChannel(commands.CommandError):
    pass


class NoVoiceChannel(commands.CommandError):
    pass


class QueueIsEmpty(commands.CommandError):
    pass


class NoTracksFound(commands.CommandError):
    pass


class PlayerIsAlreadyPaused(commands.CommandError):
    pass


class NoMoreTracks(commands.CommandError):
    pass


class NoPreviousTracks(commands.CommandError):
    pass


class NotConnectedToChannel(commands.CommandError):
    pass

class NoCurrentTrack(commands.CommandError):
    pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.start_nodes())
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Disconnect from the voice channel if the bot is the only one left in the channel."""
        if not member.bot and after.channel is None:
            await asyncio.sleep(300)
            if not [m for m in before.channel.members if not m.bot]:
                guild = member.guild
                vc: wavelink.Player = guild.voice_client
                await vc.disconnect()
                
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"Wavelink node '{payload.node.identifier}' ready.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Play the next track in the queue if there is one."""
        if payload.reason != "FINISHED":
            return
        
        if not payload.player.queue.is_empty:
            track = await payload.player.play(track=payload.player.queue.get(), populate=payload.player.autoplay)
            await self.text.send(f"Now playing: {track.title}")
        elif not payload.player.auto_queue.is_empty:
            track = await payload.player.play(track=payload.player.auto_queue.get(), populate=payload.player.autoplay)
            # Ensure self.text is a valid channel object. It should be set by commands like play/connect.
            if hasattr(self, 'text') and self.text:
                 await self.text.send(f"Now playing: {track.title}")
            else:
                # Fallback or error logging if self.text is not set
                print(f"Error: self.text not set in on_wavelink_track_end for player {payload.player.guild_id}")


    # Removed cog_check, slash commands can be guild_only or check interaction.guild

    async def start_nodes(self):
        """Start the wavelink node."""
        await self.bot.wait_until_ready()
        node: wavelink.Node = wavelink.Node(uri='http://127.0.0.1:2333', password='youshallnotpass')
        await wavelink.Pool.connect(client=self.bot, nodes=[node])

    @app_commands.command(name="connect", description="Connects the bot to your voice channel.")
    async def connect_command(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            raise NoVoiceChannel("You are not connected to a voice channel.") # Custom error, will be caught by cog_app_command_error

        channel = interaction.user.voice.channel
        vc: wavelink.Player = interaction.guild.voice_client

        if vc:
            if vc.channel == channel:
                raise AlreadyConnectedToChannel(f"Already connected to {channel.mention}.")
            try:
                await vc.move_to(channel)
                self.vc = vc
                self.text = interaction.channel # Update text channel
                await interaction.response.send_message(f"Moved to {channel.mention}.")
            except asyncio.TimeoutError:
                await interaction.response.send_message(f"Timed out moving to {channel.mention}.", ephemeral=True)
            return

        try:
            new_vc = await channel.connect(cls=wavelink.Player)
            self.vc = new_vc
            self.text = interaction.channel # Set text channel on new connection
            await interaction.response.send_message(f"Connected to {channel.mention}.")
        except Exception as e:
            # Fallback for other connection errors
            print(f"Error connecting to voice channel: {e}")
            await interaction.response.send_message(f"Failed to connect to {channel.mention}. Reason: {e}", ephemeral=True)


    @app_commands.command(name="disconnect", description="Disconnects the bot from the voice channel.")
    async def disconnect_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            raise NotConnectedToChannel("Not connected to any voice channel.")

        await vc.disconnect()
        self.vc = None # Clear vc instance
        # self.text = None # Optionally clear text channel too, or leave for potential future use
        await interaction.response.send_message("Disconnected.")

    @app_commands.command(name="play", description="Plays a song or adds it to the queue. Resumes if paused and no query.")
    @app_commands.describe(query="Song name or URL. Leave empty to resume playback if paused.")
    async def play_command(self, interaction: discord.Interaction, query: t.Optional[str] = None):
        await interaction.response.defer() # Defer response as searching/connecting can take time

        vc: wavelink.Player = interaction.guild.voice_client
        if not vc: # Not connected, try to connect
            if not interaction.user.voice:
                raise NoVoiceChannel("You must be in a voice channel to play music.")
            vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            self.vc = vc

        # Ensure self.vc is set, especially if connected by a previous command in the same session
        if not self.vc:
            self.vc = vc
        
        self.text = interaction.channel # Update text channel for announcements

        if query is None:
            if self.vc.is_paused():
                if self.vc.current is None and self.vc.queue.is_empty: # Check if there's anything to resume
                    raise QueueIsEmpty("Queue is empty and nothing is paused to resume.")
                await self.vc.resume()
                await interaction.followup.send("Playback resumed.")
            elif self.vc.is_playing():
                raise PlayerIsAlreadyResumed("Player is already playing.")
            else: # Not paused, not playing, but query is None means "resume" was intended
                if self.vc.queue.is_empty:
                    raise QueueIsEmpty("Queue is empty. Provide a song name or URL to play.")
                # If something is in queue but not playing (e.g. after stop or if first play failed to start)
                current_track = self.vc.queue.get()
                await self.vc.play(track=current_track, populate=self.vc.autoplay)
                await interaction.followup.send(f"Now playing: {current_track.title}")

        else: # Query is provided
            tracks = await wavelink.Playable.search(query) # Use Playable.search for broader search
            if not tracks:
                raise NoTracksFound(f"No tracks found for query: `{query}`.")

            if isinstance(tracks, wavelink.Playlist):
                added = await self.vc.queue.put_wait(tracks.tracks) # Use put_wait for playlists
                await interaction.followup.send(f"Added {added} tracks from playlist {tracks.name} to the queue.")
            else: # Single track
                track = tracks[0] # search returns a list
                await self.vc.queue.put_wait(track)
                await interaction.followup.send(f"Added `{track.title}` to the queue.")

            if not self.vc.is_playing(): # If not already playing, start playback
                current_track = self.vc.queue.get()
                await self.vc.play(track=current_track, populate=self.vc.autoplay)
                # followup already sent for adding to queue, on_wavelink_track_end will announce "Now playing"

    @app_commands.command(name="pause", description="Pauses the current track.")
    async def pause_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            raise NotConnectedToChannel("Not connected to a voice channel.")

        # Use self.vc if available and connected, otherwise use vc from interaction
        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if not player_to_use.is_playing(): # Includes if nothing is loaded/playing
            raise PlayerIsAlreadyPaused("Player is not currently playing anything or is already paused.")

        if player_to_use.is_paused(): # Specifically already paused
             raise PlayerIsAlreadyPaused("Player is already paused.")

        await player_to_use.pause()
        await interaction.response.send_message("Playback paused.")

    @app_commands.command(name="resume", description="Resumes the current track if paused.")
    async def resume_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            raise NotConnectedToChannel("Not connected to a voice channel.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if not player_to_use.is_paused():
            # This also covers the case where nothing is loaded/playing, as is_paused would be false.
            raise PlayerIsAlreadyResumed("Player is not paused or nothing to resume.")

        # No need to check queue_is_empty specifically here, as if it was empty and not paused,
        # the above check would catch it. If it's paused, it implies there's a current track.
        await player_to_use.resume()
        await interaction.response.send_message("Playback resumed.")

    @app_commands.command(name="stop", description="Stops playback and clears the queue.")
    async def stop_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            raise NotConnectedToChannel("Not connected to a voice channel.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if not player_to_use.is_playing() and player_to_use.queue.is_empty:
             await interaction.response.send_message("Nothing is playing and the queue is empty.", ephemeral=True)
             return

        player_to_use.queue.clear()
        await player_to_use.stop() # Stops current track and clears it
        await interaction.response.send_message("Playback stopped and queue cleared.")

    @app_commands.command(name="next", description="Skips to the next song in the queue.")
    async def next_command(self, interaction: discord.Interaction): # Aliases like "skip" are not directly supported
        await interaction.response.defer()
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            raise NotConnectedToChannel("Not connected to a voice channel.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if player_to_use.queue.is_empty:
            if not player_to_use.autoplay or player_to_use.auto_queue.is_empty: # Check autoplay queue
                raise QueueIsEmpty("Queue is empty and no song to skip to.")
            # If only auto_queue has songs, stop() will trigger track_end, which should play from auto_queue.

        await player_to_use.stop() # stop() triggers on_wavelink_track_end, which plays next if available
        await interaction.followup.send("Skipped to the next track. If available, it will play shortly.")


    @app_commands.command(name="previous", description="Plays the previous song from history.")
    async def previous_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            raise NotConnectedToChannel("Not connected to a voice channel.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if player_to_use.queue.history.count == 0:
            raise NoPreviousTracks("No tracks in history to play.")

        # Logic for 'previous' can be complex. Wavelink's history is a FiFo.
        # history.pop() gets the *most recently played* (which could be the current track).
        # To get the actual "previous", we might need to manipulate history carefully.

        # Simplified approach:
        # 1. If a track is currently playing, stop it and temporarily store it.
        # 2. Get the last track from history (this will be the one that just finished or was current).
        # 3. If the stored current track is different from this, it implies we want the one before the stored current.
        #    This part is tricky.

        # Let's try a more direct interpretation: Play the track that was playing before the current one.
        # If nothing is playing, play the last played track.

        history_snapshot = list(player_to_use.queue.history) # Get a copy of history items

        if not history_snapshot:
            raise NoPreviousTracks("History is empty.")

        target_track_to_play_info = None

        if player_to_use.current:
            # Current track is playing. We want the one before it.
            # The current track is the last element in history_snapshot.
            if len(history_snapshot) >= 2:
                target_track_to_play_info = history_snapshot[-2] # The one before current
            else:
                # Only the current song in history, can't go "previous" to it in this sense.
                # Depending on desired behavior, could replay current or error.
                # For now, error if only current exists.
                raise NoPreviousTracks("Only the current song is in history. Cannot go to a 'previous' distinct song.")
        else:
            # Nothing is currently playing. Play the most recent item from history.
            target_track_to_play_info = history_snapshot[-1]

        if not target_track_to_play_info:
            raise NoPreviousTracks("Could not determine the previous track.")

        # Stop the current player and clear the immediate "next up" if any, but don't modify main queue yet
        await player_to_use.stop(populate=False)
        player_to_use.queue.put_at_front(target_track_to_play_info) # Put the target previous track at the front

        # Wavelink player's `play` method automatically manages history.
        # When we play `target_track_to_play_info`, it will be added to history again.
        # This is generally acceptable.

        await player_to_use.play(player_to_use.queue.get()) # Play the track we just put at front

        await interaction.followup.send(f"Now playing previous track: `{target_track_to_play_info.title}`")

    @app_commands.command(name="queue", description="Shows the current song queue.")
    @app_commands.describe(show="Number of tracks to display in the queue (up to 25).")
    async def queue_command(self, interaction: discord.Interaction, show: t.Optional[app_commands.Range[int, 1, 25]] = 10):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.is_connected(): # vc.is_connected() might be redundant if vc is None
            raise NotConnectedToChannel("Not connected to a voice channel to view the queue.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if player_to_use.queue.is_empty and player_to_use.queue.history.is_empty and not player_to_use.current:
            raise QueueIsEmpty("The queue is currently empty.")

        embed = discord.Embed(
            title="Music Queue",
            # description=f"Showing the next {show} tracks.", # Description can be part of fields
            colour=interaction.user.colour if hasattr(interaction.user, 'colour') else discord.Color.blue(), # User might be from DM
            timestamp=dt.datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)

        current_track_title = getattr(player_to_use.current, "title", "No track currently playing.")
        current_track_value = f"[{current_track_title}]({getattr(player_to_use.current, 'uri', '#')})" if player_to_use.current else current_track_title
        embed.add_field(name="Currently Playing", value=current_track_value, inline=False)
        
        if not player_to_use.queue.is_empty:
            next_up_tracks = list(player_to_use.queue)[:show]
            next_up_value = "\n".join(f"{i+1}. [{track.title}]({track.uri})" for i, track in enumerate(next_up_tracks))
            if not next_up_value: next_up_value = "Queue is empty."
            embed.add_field(name=f"Next Up (Top {show})", value=next_up_value, inline=False)
        else:
            embed.add_field(name=f"Next Up (Top {show})", value="Queue is empty.", inline=False)

        if not player_to_use.queue.history.is_empty:
            # Show recent history, similar to 'show' limit for next up
            history_tracks = list(player_to_use.queue.history)[-show:] # Get last 'show' items
            history_tracks.reverse() # To show most recent first
            history_value = "\n".join(f"- [{track.title}]({track.uri})" for track in history_tracks)
            if not history_value: history_value = "No tracks in history."
            embed.add_field(name=f"Recently Played (Last {show})", value=history_value, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="repeat", description="Sets the repeat mode for the queue.")
    @app_commands.describe(mode="Choose repeat mode: 'none', 'song', or 'all'.")
    @app_commands.choices(mode=[
        app_commands.Choice(name="None", value="none"),
        app_commands.Choice(name="Song", value="song"),
        app_commands.Choice(name="All", value="all"),
    ])
    async def repeat_command(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc: # Checking self.vc as well, as it might be the active player instance
             if self.vc and self.vc.is_connected():
                 vc = self.vc
             else:
                 raise NotConnectedToChannel("Not connected to a voice channel.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        repeat_mode_map = {
            "none": wavelink.QueueMode.normal,
            "song": wavelink.QueueMode.loop,      # Loop current song
            "all":  wavelink.QueueMode.loop_all,  # Loop entire queue
        }
        
        selected_mode = repeat_mode_map.get(mode.value.lower())

        if selected_mode is None: # Should not happen with choices, but good practice
            raise InvalidRepeatMode("Invalid repeat mode selected. Use 'none', 'song', or 'all'.")

        player_to_use.queue.mode = selected_mode

        await interaction.response.send_message(f"Repeat mode set to: **{mode.name}**.")

    @app_commands.command(name="clear", description="Clears the song queue.")
    async def clear_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            if self.vc and self.vc.is_connected():
                vc = self.vc
            else:
                raise NotConnectedToChannel("Not connected to a voice channel to clear the queue.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        if player_to_use.queue.is_empty:
            await interaction.response.send_message("The queue is already empty.", ephemeral=True)
            return

        player_to_use.queue.clear()
        await interaction.response.send_message("Queue cleared successfully.")

    @app_commands.command(name="autoplay", description="Toggles autoplay for recommended songs.")
    async def autoplay_command(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            if self.vc and self.vc.is_connected():
                vc = self.vc
            else:
                raise NotConnectedToChannel("Not connected to a voice channel to toggle autoplay.")

        player_to_use = self.vc if self.vc and self.vc.is_connected() else vc

        # Wavelink player's autoplay can be wavelink.AutoPlayMode.enabled or wavelink.AutoPlayMode.partial or wavelink.AutoPlayMode.disabled
        # For a simple toggle, we'll switch between enabled and disabled.
        if player_to_use.autoplay == wavelink.AutoPlayMode.enabled:
            player_to_use.autoplay = wavelink.AutoPlayMode.disabled
            await interaction.response.send_message("Autoplay disabled.")
        else:
            player_to_use.autoplay = wavelink.AutoPlayMode.enabled
            await interaction.response.send_message("Autoplay enabled. Recommended songs will play when the queue is empty.")

    @app_commands.command(name="forceplay", description="Plays a song immediately, adding it to the front of the queue.")
    @app_commands.describe(query="The song name or URL to play immediately.")
    async def forceplay_command(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client
        if not vc: # Not connected, try to connect
            if not interaction.user.voice:
                raise NoVoiceChannel("You must be in a voice channel to force play music.")
            vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            self.vc = vc

        if not self.vc: # Ensure self.vc is set
            self.vc = vc

        self.text = interaction.channel # Update text channel

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            raise NoTracksFound(f"No tracks found for query: `{query}`.")

        track_to_play = None
        if isinstance(tracks, wavelink.Playlist):
            # For forceplay with a playlist, typically play the first song and add rest to front of queue
            track_to_play = tracks.tracks[0]
            for i, track_item in reversed(list(enumerate(tracks.tracks))):
                if i == 0: continue # Skip first, it's track_to_play
                self.vc.queue.put_at_front(track_item)
            await interaction.followup.send(f"Force playing `{track_to_play.title}`. Added {len(tracks.tracks)-1} other tracks to the front of the queue.")
        else: # Single track
            track_to_play = tracks[0]
            await interaction.followup.send(f"Force playing `{track_to_play.title}`.")

        # Stop current track before playing the new one if already playing
        if self.vc.is_playing() or self.vc.current:
            await self.vc.stop(populate=False) # stop without populating next from queue

        self.vc.queue.put_at_front(track_to_play) # Add the main track to the very front

        # Play the track now at the front
        # This should be handled by on_wavelink_track_end after stop, or if not playing, it should start.
        # However, to ensure it plays immediately after being added to front:
        if not self.vc.is_playing():
             await self.vc.play(self.vc.queue.get(), populate=self.vc.autoplay)
        # If it was playing, the stop() + queue manipulation should lead to it.
        # The track_end event might fire from stop(), and then play this.
        # Explicitly calling play if not playing ensures it starts.
        # If it was playing, the stop should have cleared current, and track_end will pick this up.

    @app_commands.command(name="search", description="Searches for a song and shows results to choose from.")
    @app_commands.describe(query="The song name to search for.")
    async def search_command(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            if self.vc and self.vc.is_connected(): # Check if self.vc exists from a previous command
                vc = self.vc
            elif interaction.user.voice: # If user is in a channel, connect
                vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                self.vc = vc
            else: # No existing VC and user not in a channel
                raise NoVoiceChannel("Bot is not in a voice channel and you are not connected to one.")

        if not self.vc: self.vc = vc # Ensure self.vc is set
        self.text = interaction.channel # Set text channel

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            raise NoTracksFound(f"No tracks found for your search: `{query}`.")

        if isinstance(tracks, wavelink.Playlist):
            await interaction.followup.send(f"Found a playlist: `{tracks.name}` with `{len(tracks.tracks)}` tracks. Use the play command to add it.")
            return

        # Create an embed with search results
        embed = discord.Embed(title="Search Results", description=f"Found these tracks for `{query}`:", color=discord.Color.og_blurple())
        results_to_show = min(len(tracks), 5) # Show top 5 results
        
        view = discord.ui.View()

        for i, track in enumerate(tracks[:results_to_show]):
            embed.add_field(name=f"{i+1}. {track.title}", value=f"Duration: {str(dt.timedelta(milliseconds=track.length))}", inline=False)
            view.add_item(SelectTrackButton(track=track, music_cog=self, original_interaction=interaction)) # Pass cog and interaction

        await interaction.followup.send(embed=embed, view=view)

# Helper UI element for search
class SelectTrackButton(discord.ui.Button['Music']):
    def __init__(self, track: wavelink.Playable, music_cog: Music, original_interaction: discord.Interaction):
        super().__init__(label=f"Play {track.title[:50]}...", style=discord.ButtonStyle.primary, custom_id=f"select_{track.identifier[:90]}")
        self.track = track
        self.music_cog = music_cog
        self.original_interaction = original_interaction # Store original interaction to use its channel for followup

    async def callback(self, interaction: discord.Interaction):
        # This interaction is for the button click
        await interaction.response.defer() # Acknowledge button click

        vc = self.music_cog.vc # Use the stored VC from the Music cog
        if not vc or not vc.is_connected():
            # Try to use original interaction's guild voice client if user still there
            if self.original_interaction.user.voice:
                vc = await self.original_interaction.user.voice.channel.connect(cls=wavelink.Player)
                self.music_cog.vc = vc
            else:
                await interaction.followup.send("Could not connect or find voice client.", ephemeral=True)
                return

        self.music_cog.text = self.original_interaction.channel # Ensure text channel is from original command

        await vc.queue.put_wait(self.track)

        # Edit the original message (buttons) to indicate selection, or send new message
        # For simplicity, send a new message via followup from the button interaction
        await interaction.followup.send(f"Added `{self.track.title}` to the queue.")

        if not vc.is_playing():
            current_track = vc.queue.get()
            await vc.play(track=current_track, populate=vc.autoplay)
            # "Now playing" will be announced by on_wavelink_track_end via self.music_cog.text


    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for app commands in this cog."""
        # Default error message
        error_message = f"An unexpected error occurred: {error}"
        ephemeral = True # Most errors should be ephemeral

        # Handle custom exceptions
        # Specific error types from this cog
        custom_errors = (
            PlayerIsAlreadyResumed, AlreadyConnectedToChannel, NoVoiceChannel,
            QueueIsEmpty, PlayerIsAlreadyPaused, NoMoreTracks,
            NoPreviousTracks, NotConnectedToChannel, NoCurrentTrack,
            InvalidRepeatMode, NoTracksFound, IncorrectArgumentType
        )
        if isinstance(error, custom_errors):
            error_message = str(error)
        elif isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, custom_errors):
             error_message = str(error.original)

        # Check if wavelink specific errors might need specific handling
        elif isinstance(error, wavelink.WavelinkException):
            error_message = f"Wavelink error: {error}"
            # Potentially log more details for wavelink errors
            print(f"Wavelink Error: {error}")
        elif isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, wavelink.WavelinkException):
            error_message = f"Wavelink error: {error.original}"
            print(f"Wavelink Error via Invoke: {error.original}")


        # Log the error
        print(f"Error in cog {self.qualified_name}, command {interaction.command.name if interaction.command else 'Unknown'}: {error}")
        # You might want to use self.bot.logger or a dedicated logger here
        # logging.error(f"Error in cog {self.qualified_name}, command {interaction.command.name if interaction.command else 'Unknown'}: {error}", exc_info=error)


        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=ephemeral)
        else:
            # If defer() has been used, followup is required.
            # However, if not deferred and response not sent, send_message is fine.
            try:
                await interaction.response.send_message(error_message, ephemeral=ephemeral)
            except discord.errors.InteractionResponded:
                 await interaction.followup.send(error_message, ephemeral=ephemeral)
            except Exception as e: # Catch other potential issues like client not having permissions
                print(f"Failed to send error message: {e}")
                # Fallback, maybe log to a channel if direct response fails
                # await interaction.channel.send(f"Critical error handling message for: {interaction.user.mention}")


    # Removed all old @command.error decorators and help_music command. Slash commands handle this.
    # Individual commands will be refactored below.

async def setup(bot):
    await bot.add_cog(Music(bot))

