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

# Queue class

class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self.repeat_mode = RepeatMode.NONE

    @property
    def first_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    @property
    def is_empty(self):
        return not self._queue

    @property
    def current_track(self):
        if not self._queue:
            raise QueueIsEmpty
        if self.position <= len(self._queue) - 1:
            return self._queue[self.position]

    @property
    def upcoming_tracks(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[self.position + 1:]

    @property
    def history(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[:self.position]

    @property
    def length(self):
        return len(self._queue)

    def empty_queue(self):
        self._queue.clear()
        self.position = 0

    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty

        self.position += 1

        if self.position < 0:
            return None
        elif self.position > len(self._queue) - 1:
            if self.repeat_mode == RepeatMode.ALL:
                self.position = 0
            else:
                return None
        
        return self._queue[self.position]

    def shuffle(self):
        if not self._queue:
            raise QueueIsEmpty

        upcoming = self.upcoming_tracks
        random.shuffle(upcoming)

        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)

    def get_track_title(self, position):
        if not self._queue:
            raise QueueIsEmpty

        if position < 0:
            return self._queue[len(self._queue) - 1]
        elif position > len(self._queue) - 1:
            return self.first_track

        return self._queue[position]

    def set_repeat_mode(self, mode):
        if mode == "none":
            self.repeat_mode = RepeatMode.NONE
        elif mode == "song":
            self.repeat_mode = RepeatMode.SONG
        else:
            self.repeat_mode = RepeatMode.ALL

    def add(self, *args):
        self._queue.extend(args)

    def insert_next(self, *args):
        if not self._queue:
            raise QueueIsEmpty

        upcoming = self.upcoming_tracks
        self._queue = self._queue[:self.position + 1]
        self._queue.extend(args)
        self._queue.extend(upcoming)

    def clear_upcoming(self):
        if not self._queue:
            raise QueueIsEmpty

        self._queue = self._queue[:self.position + 1]


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.destroy()
        except KeyError:
            pass

    async def add_tracks(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
            await ctx.send(f"Added {tracks.tracks[0].title} and {len(tracks.tracks) - 1} other songs to the queue.")

        elif len(tracks) >= 1:
            self.queue.add(tracks[0])
            await ctx.send(f"Added {tracks[0].title} to the queue.")

        else: 
            raise NoTracksFound

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()

    async def search_tracks(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            raise IncorrectArgumentType

        elif (track := await self.choose_track(ctx, tracks)) is not None:
                self.queue.add(track)
                await ctx.send(f"Added {track.title} to the queue.")
        else:
            raise NoTracksFound

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()

    async def force_add_track(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.insert_next(*tracks.tracks)
            await ctx.send(f"Added {tracks.tracks[0].title} and {len(tracks.tracks) - 1} other songs to the queue.")
            
        elif len(tracks.tracks) == 1:
            self.queue.insert_next(tracks[0])
            await ctx.send(f"Added {tracks[0].title} to the queue.")
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None:
                self.queue.insert_next(track)
                await ctx.send(f"Added {track.title} to the queue.")

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()

    async def choose_track(self, ctx, tracks):
        def _check(r, u):
            return (
                r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Choose a song",
            description=(
                "\n".join(
                    f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
                    for i, t in enumerate(tracks[:5])
                )
            ),
            colour=ctx.author.colour,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Invoked by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()
        else:
            await msg.delete()
            return tracks[OPTIONS[reaction.emoji]]

    async def start_playback(self):
        await self.play(self.queue.current_track)

    async def advance(self):
        try: 
           if (track := self.queue.get_next_track()) is not None:
                await self.play(track)
        except QueueIsEmpty:
            pass

    async def repeat_track(self):
        await self.play(self.queue.current_track)


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            await asyncio.sleep(300)
            if not [m for m in before.channel.members if not m.bot]:
                await self.get_player(member.guild).teardown()
                
    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node '{node.identifier}' ready.")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        if payload.player.queue.repeat_mode == RepeatMode.SONG:
            await payload.player.repeat_track()
        else:
            await payload.player.advance()


    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are not available in direct messages.")
            return False

        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        nodes = {
            "MAIN" : {
                "host": "127.0.0.1",
                "port": 2333,
                "rest_uri": "http://127.0.0.1:2333",
                "password": "youshallnotpass",
                "identifier": "MAIN",
                "region": "sydney",
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx, *, channel:t.Optional[discord.VoiceChannel]):
        """Connects to the channel the user is in or to the one given in the argument."""
        player = self.get_player(ctx)
        channel = await player.connect(ctx, channel)
        await ctx.send(f"Connected to {channel.name}.")
   
    @connect_command.error
    async def connect_command_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send("Already connected to a voice channel.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suiteable voice channel was provided.")

    @commands.command(name="disconnect", aliases=["leave"])
    async def disconnect_command(self, ctx,):
        """Disconnects from the channel."""
        player = self.get_player(ctx)
        await player.teardown()
        await ctx.send("Disconnected.")

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)
        
        if query is None:
            if player.is_playing:
                raise PlayerIsAlreadyResumed

            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
            await ctx.send("Playback resumed.")

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"

            await player.add_tracks(ctx, await self.wavelink.get_tracks(query))

    @play_command.error
    async def play_command_error(self, ctx, exc):
        if isinstance(exc, PlayerIsAlreadyResumed):
            await ctx.send("Already playing.")
        elif isinstance(exc, QueueIsEmpty):
            await ctx.send("No songs in queue to play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")

    @commands.command(name="pause")
    async def pause_command(self, ctx):
        player = self.get_player(ctx)

        if player.is_paused:
            raise PlayerIsAlreadyPaused

        if player.queue.is_empty:
            raise QueueIsEmpty

        await player.set_pause(True)
        await ctx.send("Playback paused.")

    @pause_command.error
    async def pause_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Nothing to pause, queue is empty.")
        elif isinstance(exc, PlayerIsAlreadyPaused):
            await ctx.send("Playback is already paused.")

    @commands.command(name="resume")
    async def resume_command(self, ctx):
        player = self.get_player(ctx)

        if not player.is_paused:
            raise PlayerIsAlreadyResumed
        if player.queue.is_empty:
            raise QueueIsEmpty

        await player.set_pause(False)
        await ctx.send("Playback resumed.")

    @commands.command(name="stop")
    async def stop_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.empty_queue()
        await player.stop()
        await ctx.send("Playback stopped.")

    @commands.command(name="next", aliases=["skip"])
    async def next_command(self, ctx):
        player = self.get_player(ctx)
        if not player.queue.upcoming_tracks and not player.queue.repeat_mode == RepeatMode.ALL:
            raise NoMoreTracks

        await player.stop()
        await ctx.send(f"Playing next track: {player.queue.get_track_title(player.queue.position + 1)}")

    @next_command.error
    async def next_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The skip could not be executed as the queue is currently empty.")
        elif isinstance(exc, NoMoreTracks):
            await ctx.send("There are no more tracks in the queue.")

    @commands.command(name="previous")
    async def previous_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.history and not player.queue.repeat_mode == RepeatMode.ALL:
            raise NoPreviousTracks

        player.queue.position -= 2
        
        if player.queue.position <= -2:
            player.queue.position = player.queue.length - 2

        await player.stop()
        await ctx.send(f"Playing previous track: {player.queue.get_track_title(player.queue.position + 1)}.\nIndex: {player.queue.position + 1}.")

    @previous_command.error
    async def previous_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The skip could not be execture as the queue is currently empty.")
        elif isinstance(exc, NoPreviousTracks):
            await ctx.send("There are no previous tracks in queue.")

    @commands.command(name="queue")
    async def queue_command(self, ctx, show: t.Optional[int] = 10):
        player = self.get_player(ctx)
        if player.queue.is_empty:
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
            value=getattr(player.queue.current_track, "title", "No tracks currently playing!"), 
            inline=False
        )
        
        if previous := player.queue.history:
            embed.add_field(
                name="Previously played",
                value="\n".join(" - " + t.title for t in previous[len(previous) - 10:]),
                inline=False
            )

        if upcoming := player.queue.upcoming_tracks:
            embed.add_field(
                name="Next up",
                value="\n".join(" - " + t.title for t in upcoming[:show]),
                inline=False
            )

        await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The queue is currently empty.")

    @commands.command(name="shuffle")
    async def shuffle_command(self, ctx):
        player = self.get_player(ctx)

        player.queue.shuffle()
        await ctx.send("Queue shuffled.")

    @shuffle_command.error
    async def shuffle_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("The queue could not be shuffled as it is currently empty.")

    @commands.command(name="repeat")
    async def repeat_command(self, ctx, mode: str):
        if mode is None:
            raise MissingArgument
        elif mode not in ("none", "song", "all"):
            raise InvalidRepeatMode
        
        player = self.get_player(ctx)
        player.queue.set_repeat_mode(mode)
        await ctx.send(f"The repeat mode has been set to {mode}.")

    @repeat_command.error
    async def repeat_command_error(self, ctx, exc):
        if isinstance(exc, MissingArgument):
            await ctx.send("No argument supplied.")
        elif isinstance(exc, InvalidRepeatMode):
            await ctx.send("Incorrect argument supplied.")

    @commands.command(name="forceplay", aliases=["force"])
    async def forceplay_command(self, ctx, *, query: str):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)
        
        if query is None:
            raise MissingArgument

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"

            await player.force_add_track(ctx, await self.wavelink.get_tracks(query))
            await player.stop()
            
    @forceplay_command.error
    async def forceplay_command_error(self, ctx, exc):
        if isinstance(exc, MissingArgument):
            await ctx.send("Missing song to force play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")

    @commands.command(name="clear")
    async def clear_command(self, ctx):
        player = self.get_player(ctx)

        if player.queue.upcoming_tracks:
            player.queue.clear_upcoming()

        await ctx.send("Queue cleared.")

    @clear_command.error
    async def clear_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No queue to clear.")

    @commands.command(name="search")
    async def search_command(self, ctx, *, query: str):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)
        
        if query is None:
            if player.is_playing:
                raise PlayerIsAlreadyResumed

            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
            await ctx.send("Playback resumed.")

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"

            await player.search_tracks(ctx, await self.wavelink.get_tracks(query))

    @search_command.error
    async def search_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No songs in queue to play.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel was provided.")
        elif isinstance(exc, IncorrectArgumentType):
            await ctx.send("Incorrect argument supplied to search.")


def setup(bot):
    bot.add_cog(Music(bot))

