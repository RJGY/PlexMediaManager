import asyncio
import datetime as dt
import enum
from itertools import repeat

import typing as t
import random
import re

import discord
import wavelink
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
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        print(f"Wavelink node '{node.id}' ready.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEventPayload):
        """Play the next track in the queue if there is one."""
        if payload.reason != "FINISHED":
            return
        
        if not payload.player.queue.is_empty:
            track = await payload.player.play(track=payload.player.queue.get(), populate=payload.player.autoplay)
            await self.text.send(f"Now playing: {track.title}")
        elif not payload.player.auto_queue.is_empty:
            track = await payload.player.play(track=payload.player.auto_queue.get(), populate=payload.player.autoplay)
            await self.text.send(f"Now playing: {track.title}")

    async def cog_check(self, ctx: commands.Context):
        """A check to make sure we are not in a discord DM channel."""
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are not available in direct messages.")
            return False

        return True

    async def start_nodes(self):
        """Start the wavelink node."""
        await self.bot.wait_until_ready()
        node: wavelink.Node = wavelink.Node(uri='https://127.0.0.1:2333', password='youshallnotpass')
        await wavelink.NodePool.connect(client=self.bot, nodes=[node])
        

    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx: commands.Context):
        """Connect to a voice channel."""
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            self.vc = vc
            self.text = ctx.channel
        else:
            vc: wavelink.Player = ctx.voice_client
            self.vc = vc

        await ctx.send("Connected.")
   
    @connect_command.error
    async def connect_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send("Already connected to a voice channel.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suiteable voice channel was provided.")

    @commands.command(name="disconnect", aliases=["leave"])
    async def disconnect_command(self, ctx: commands.Context):
        """Disconnect from a voice channel."""
        vc: wavelink.Player = ctx.voice_client
        await vc.disconnect()
        await ctx.send("Disconnected.")
        self.vc = None

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx: commands.Context, *, query: t.Optional[str]):
        """Play a song from YouTube."""
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            self.vc = vc
            self.text = ctx.channel
        else:
            vc: wavelink.Player = ctx.voice_client
            self.vc = vc
        
        if query is None:
            if vc.is_playing():
                raise PlayerIsAlreadyResumed

            if vc.queue.is_empty:
                raise QueueIsEmpty

            await vc.resume()
            await ctx.send("Playback resumed.")

        else:
            track = await wavelink.YouTubeTrack.search(query, return_first=True)

            if isinstance(track, wavelink.YouTubeTrack):
                vc.queue.put(track)
            elif isinstance(track, wavelink.YouTubePlaylist):
                for t in track.tracks:
                    vc.queue.put(t)
                await ctx.send(f"Added {len(track.tracks)} tracks to queue.")

            if vc.current is None:
                current_track = vc.queue.get()
                await vc.play(track=current_track, populate=vc.autoplay)
                await ctx.send(f"Now playing {current_track.title}.")
            elif vc.current is not None and isinstance(track, wavelink.YouTubeTrack):
                await ctx.send(f"Added {track.title} to queue.")


    @play_command.error
    async def play_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, PlayerIsAlreadyResumed):
            await ctx.send("Already playing.")
        elif isinstance(exc, QueueIsEmpty):
            await ctx.send("No songs in queue to play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")

    @commands.command(name="pause")
    async def pause_command(self, ctx: commands.Context):
        """Pause the current track."""
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = self.vc

        if vc.is_paused():
            raise PlayerIsAlreadyPaused
        
        if vc.queue.is_empty and vc.current is None:
            raise QueueIsEmpty

        await vc.pause()
        await ctx.send("Playback paused.")

    @pause_command.error
    async def pause_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Nothing to pause, queue is empty.")
        elif isinstance(exc, PlayerIsAlreadyPaused):
            await ctx.send("Player is already paused.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="resume")
    async def resume_command(self, ctx: commands.Context):
        """Resume the current track."""
        if not ctx.voice_client:
            raise NotConnectedToChannel

        vc: wavelink.Player = self.vc

        if not vc.is_paused():
            raise PlayerIsAlreadyResumed
        
        if vc.queue.is_empty and vc.current is None:
            raise QueueIsEmpty

        await vc.resume()
        await ctx.send("Playback resumed.")

    @resume_command.error
    async def resume_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Nothing to resume, queue is empty.")
        elif isinstance(exc, PlayerIsAlreadyResumed):
            await ctx.send("Player is already playing.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="stop")
    async def stop_command(self, ctx: commands.Context):
        """Stop the current track and clears the queue."""
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = self.vc

        vc.queue.clear()
        await vc.stop()
        await ctx.send("Playback stopped and Queue cleared.")

    @stop_command.error
    async def stop_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="next", aliases=["skip"])
    async def next_command(self, ctx: commands.Context):
        """Skip the current track."""
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = self.vc

        if vc.queue.is_empty:
            raise QueueIsEmpty
        
        track = await vc.play(track=vc.queue.get(), populate=vc.autoplay)
        await ctx.send(f"Now playing {track.title}.")

    @next_command.error
    async def next_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The skip could not be executed as the queue is currently empty.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="previous")
    async def previous_command(self, ctx: commands.Context):
        """Play the previous track."""
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = self.vc

        if not vc.queue.history or len(vc.queue.history) < 2:
            raise NoPreviousTracks
        
        if not vc.current:
            raise NoCurrentTrack

        current_track = vc.queue.history.pop()
        previous_track = vc.queue.history.pop()
        vc.queue.put_at_front(current_track)
        vc.queue.put_at_front(previous_track)
        track = await vc.play(track=vc.queue.get(), populate=vc.autoplay)

        await ctx.send(f"Playing previous track: {track.title}.")

    @previous_command.error
    async def previous_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NoPreviousTracks):
            await ctx.send("There are no previous tracks in queue.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")
        elif isinstance(exc, NoCurrentTrack):
            await ctx.send("There is no current track playing.")

    @commands.command(name="queue")
    async def queue_command(self, ctx: commands.Context, show: t.Optional[int] = 10):
        """Show the current queue, what is currently playing and what is next as well as previous tracks."""
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = self.vc

        if  vc.queue.is_empty and vc.queue.history.is_empty:
            raise QueueIsEmpty

        embed = discord.Embed(
            title="Queue",
            description=f"Showing the next and previous {show} tracks", 
            colour=ctx.author.colour,
            timestamp=dt.datetime.utcnow()
        )

        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.add_field(
            name="Currently Playing", 
            value=getattr(vc.current, "title", "No tracks currently playing!"), 
            inline=False
        )
        
        if not vc.queue.history.is_empty and vc.queue.history.count > 1:
            embed.add_field(
                name="Previously Played",
                value="\n".join(" - " + track.title for track in list(vc.queue.history)[vc.queue.history.count - show:-1]),
                inline=False
            )

        if not vc.queue.is_empty:
            embed.add_field(
                name="Next Up",
                value="\n".join(" - " + track.title for track in list(vc.queue)[:show]),
                inline=False
            )

        await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The queue is currently empty.")

    @commands.command(name="repeat")
    async def repeat_command(self, ctx: commands.Context):
        if self.vc is None:
            raise NotConnectedToChannel
        
        vc: wavelink.Player = self.vc
        
        vc.queue.loop = not vc.queue.loop
        if vc.queue.loop:
            await ctx.send("The current song will loop indefinitely.")
        else:
            await ctx.send("Repeat mode disabled.")

    @repeat_command.error
    async def repeat_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NotConnectedToChannel):
            await ctx.send("Bot has not connected to the voice channel in this session.")

    @commands.command(name="clear")
    async def clear_command(self, ctx: commands.Context):
        """Clear the queue."""
        if self.vc is None:
            raise NotConnectedToChannel
        
        vc: wavelink.Player = ctx.voice_client

        if vc.queue:
            vc.queue.clear()

        await ctx.send("Queue cleared.")

    @clear_command.error
    async def clear_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NotConnectedToChannel):
            await ctx.send("Bot has not connected to the voice channel in this session.")

    @commands.command(name="autoplay")
    async def autoplay_command(self, ctx: commands.Context):
        """Toggle autoplay on or off."""
        if not self.vc:
            raise NotConnectedToChannel
        
        vc: wavelink.Player = ctx.voice_client

        vc.autoplay = not vc.autoplay

        if vc.autoplay:
            await ctx.send("Autoplay enabled.")
        else:
            await ctx.send("Autoplay disabled.")

    @autoplay_command.error
    async def autoplay_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NotConnectedToChannel):
            await ctx.send("Bot has not connected to the voice channel in this session.")

    @commands.command(name="forceplay")
    async def forceplay_command(self, ctx: commands.Context, *, query: str):
        """Play a song from YouTube."""
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            self.vc = vc
            self.text = ctx.channel
        else:
            vc: wavelink.Player = ctx.voice_client
            self.vc = vc
    
        track = await wavelink.YouTubeTrack.search(query, return_first=True)

        if isinstance(track, wavelink.YouTubeTrack):
            vc.queue.put_at_front(track)
        elif isinstance(track, wavelink.YouTubePlaylist):
            old_queue = vc.queue.copy()
            vc.queue.clear()
            vc.queue.extend(track.tracks)
            vc.queue.extend(old_queue)
            await ctx.send(f"Added {len(track.tracks)} tracks to queue.")

        current_track = vc.queue.get()
        await vc.play(track=current_track, populate=vc.autoplay)
        await ctx.send(f"Now playing {current_track.title}.")

    @forceplay_command.error
    async def forceplay_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, PlayerIsAlreadyResumed):
            await ctx.send("Already playing.")
        elif isinstance(exc, QueueIsEmpty):
            await ctx.send("No songs in queue to play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")

    @commands.command(name="search")
    async def search_command(self, ctx: commands.Context, *, query: str):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        if not vc.is_connected:
            await vc.connect(ctx)
        
        if query is None:
            if vc.is_playing:
                raise PlayerIsAlreadyResumed

            if vc.queue.is_empty:
                raise QueueIsEmpty

            await vc.pause()
            await ctx.send("Playback resumed.")

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"

            track = await wavelink.YouTubeTrack.search("Ocean Drive", return_first=False)
            await vc.play(track=track, populate=vc.autoplay)

    @search_command.error
    async def search_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No songs in queue to play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")
        elif isinstance(exc, IncorrectArgumentType):
            await ctx.send("Incorrect argument supplied to search.")


async def setup(bot):
    await bot.add_cog(Music(bot))

