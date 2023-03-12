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


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.start_nodes())
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
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
        if not payload.player.queue.is_empty:
            await payload.player.play(await payload.player.queue.get())

    async def cog_check(self, ctx: commands.Context):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are not available in direct messages.")
            return False

        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        node: wavelink.Node = wavelink.Node(uri='http://localhost:2333', password='youshallnotpass')
        await wavelink.NodePool.connect(client=self.bot, nodes=[node])
        

    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        await ctx.send("Connected.")
   
    @connect_command.error
    async def connect_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send("Already connected to a voice channel.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suiteable voice channel was provided.")

    @commands.command(name="disconnect", aliases=["leave"])
    async def disconnect_command(self, ctx: commands.Context):
        vc: wavelink.Player = ctx.voice_client
        await vc.disconnect()
        await ctx.send("Disconnected.")

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx: commands.Context, *, query: t.Optional[str]):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        
        if query is None:
            if vc.is_playing():
                raise PlayerIsAlreadyResumed

            if vc.queue.is_empty:
                raise QueueIsEmpty

            await vc.resume()
            await ctx.send("Playback resumed.")

        else:
            track = await wavelink.YouTubeTrack.search(query, return_first=True)

            await vc.queue.put(track)
            if vc.current is None:
                await vc.play(track)
                await ctx.send(f"Now playing {track.title}.")
            else:
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
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = ctx.voice_client

        if vc.is_paused:
            raise PlayerIsAlreadyPaused

        if vc.queue.is_empty:
            raise QueueIsEmpty

        await vc.pause()
        await ctx.send("Playback paused.")

    @pause_command.error
    async def pause_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Nothing to pause, queue is empty.")
        elif isinstance(exc, PlayerIsAlreadyPaused):
            await ctx.send("Playback is already paused.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="resume")
    async def resume_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            raise NotConnectedToChannel

        vc: wavelink.Player = ctx.voice_client

        if not vc.is_paused:
            raise PlayerIsAlreadyResumed
        if vc.queue.is_empty:
            raise QueueIsEmpty

        await vc.resume()
        await ctx.send("Playback resumed.")

    @resume_command.error
    async def resume_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Nothing to resume, queue is empty.")
        elif isinstance(exc, PlayerIsAlreadyResumed):
            await ctx.send("Playback is already resumed.")
        elif isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="stop")
    async def stop_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = ctx.voice_client

        vc.queue.clear()
        await vc.stop()
        await ctx.send("Playback stopped.")

    @stop_command.error
    async def stop_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, NotConnectedToChannel):
            await ctx.send("Not connected to a voice channel.")

    @commands.command(name="next", aliases=["skip"])
    async def next_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            raise NotConnectedToChannel
        else:
            vc: wavelink.Player = ctx.voice_client
        if not vc.queue.get() and not vc.queue.loop_all == RepeatMode.ALL:
            raise NoMoreTracks

        await vc.get()
        await ctx.send(f"Playing next track: {vc.queue.get_track_title(vc.queue.position + 1)}")

    @next_command.error
    async def next_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The skip could not be executed as the queue is currently empty.")
        elif isinstance(exc, NoMoreTracks):
            await ctx.send("There are no more tracks in the queue.")

    @commands.command(name="previous")
    async def previous_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        if not vc.queue.history and not vc.queue.repeat_mode == RepeatMode.ALL:
            raise NoPreviousTracks

        vc.queue.position -= 2
        
        if vc.queue.position <= -2:
            vc.queue.position = vc.queue.length - 2

        await vc.stop()
        await ctx.send(f"Playing previous track: {vc.queue.get_track_title(vc.queue.position + 1)}.\nIndex: {vc.queue.position + 1}.")

    @previous_command.error
    async def previous_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The skip could not be execture as the queue is currently empty.")
        elif isinstance(exc, NoPreviousTracks):
            await ctx.send("There are no previous tracks in queue.")

    @commands.command(name="queue")
    async def queue_command(self, ctx: commands.Context, show: t.Optional[int] = 10):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        if  vc.queue.is_empty:
            raise QueueIsEmpty

        embed = discord.Embed(
            title="Queue",
            description=f"Showing the next {show} tracks", 
            colour=ctx.author.colour,
            timestamp=dt.datetime.utcnow()
        )

        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.add_field(
            name="Currently Playing", 
            value=getattr(vc.queue.current_track, "title", "No tracks currently playing!"), 
            inline=False
        )
        
        if previous := vc.queue.history:
            embed.add_field(
                name="Previously played",
                value="\n".join(" - " + t.title for t in previous[len(previous) - 10:]),
                inline=False
            )

        if upcoming := vc.queue.upcoming_tracks:
            embed.add_field(
                name="Next up",
                value="\n".join(" - " + t.title for t in upcoming[:show]),
                inline=False
            )

        await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The queue is currently empty.")

    @commands.command(name="shuffle")
    async def shuffle_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        vc.queue.shuffle()
        await ctx.send("Queue shuffled.")

    @shuffle_command.error
    async def shuffle_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The queue could not be shuffled as it is currently empty.")

    @commands.command(name="repeat")
    async def repeat_command(self, ctx: commands.Context, mode: str):
        if mode is None:
            raise MissingArgument
        elif mode not in ("none", "song", "all"):
            raise InvalidRepeatMode
        
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client
        vc.queue.set_repeat_mode(mode)
        await ctx.send(f"The repeat mode has been set to {mode}.")

    @repeat_command.error
    async def repeat_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, MissingArgument):
            await ctx.send("No argument supplied.")
        elif isinstance(exc, InvalidRepeatMode):
            await ctx.send("Incorrect argument supplied.")

    @commands.command(name="clear")
    async def clear_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        if vc.queue.upcoming_tracks:
            vc.queue.clear_upcoming()

        await ctx.send("Queue cleared.")

    @clear_command.error
    async def clear_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No queue to clear.")

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

            track = await wavelink.YouTubeTrack.search("Ocean Drive", return_first=True)
            await vc.play(track)

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

