import discord
from discord.ext import commands
import os
import pytube
import requests
import pydub
import asyncio
import ffmpeg

download_music_folder = "\\mp3s\\"
music_conversion_folder = "\\temp_music\\"
download_video_folder = "\\mp4s\\"
video_conversion_folder = "\\temp_video\\"
plex_video_folder = "\\asdf\\"
plex_music_folder = "\\asdf\\"

class IncorrectArgumentType(commands.CommandError):
    pass


class MissingArgument(commands.CommandError):
    pass


class CouldNotDecode(commands.CommandError):
    pass


class InvalidURL(commands.CommandError):
    pass


class Song:
    def __init__(self):
        self.title = ""
        self.thumb = ""
        self.artist = ""
        self.path = ""


class LocalPathCheck:
    # This function checks if the path exists. If it does not, it will create a directory there.
    # If the function cannot execute properly, it will exit.
    def path_exists(dir_path, relative):
        """Checks if the path exists. If it does not, it will create a directory there."""
        if relative:
            dir_path = os.getcwd() + dir_path
        # If the path exists, return and continue.
        if os.path.isdir(dir_path):
            return
        else:
            try:
                # If the path does not exist, make it.
                os.mkdir(dir_path)
            except OSError:
                # If error, print debug and exit.
                print("Creation of path failed. Exiting program.")
                exit()

    # This function clears the directory of all files, while leaving other directories.
    def clear_local_cache(dir_path, relative):
        """Clears the directory of all files within temporary cache directory."""
        if relative:
            dir_path = os.getcwd() + dir_path
        for file in os.listdir(dir_path):
            if os.path.isfile(dir_path + file):
                os.remove(dir_path + file)

    # This function checks the size of the directory and all files under it.
    # If the size of it is greater than one gigabyte, it will return true. else false.
    def check_cache(dir_path, relative):
        """Checks the size of the directory and all files under it. If the size of it is greater than one gigabyte, it will return true. else false."""
        if relative:
            dir_path = os.getcwd() + dir_path

        size = 0
        for folderpath, foldernames, filenames in os.walk(dir_path):
            for file in filenames:
                path = folderpath + file
                size += os.path.getsize(path)
        # Return true or false depending on whether the size of the files are greater than 1 gigabyte.
        if size > 1000000000:
            return True
        return False

    def move_video_to_plex(media):
        os.move(media, plex_video_folder)

    def move_song_to_plex(media):
        os.move(media, plex_music_folder)


class Converter:
    def __init__(self):
        self.last_converted = ""

    # This function converts any media file to an mp3.
    # This function uses pydub.
    def convert_to_mp3(self, song: Song, conversion_folder="\\MP3s\\", relative=True):
        """Converts a song from .webm to mp3."""
        # Error checking in case downloader runs into an error.
        if not isinstance(song, Song):
            raise IncorrectArgumentType

        # Error checking in case the path doesnt exist inside the dictionary
        if not song.path:
            raise MissingArgument

        videofile = song.path
        mp3name = os.path.splitext(os.path.basename(videofile))[0] + ".mp3"
        extension = os.path.splitext(os.path.basename(videofile))[1].replace(".", "")
        try:
            converted_song = pydub.AudioSegment.from_file(videofile, format=extension)
        except pydub.exceptions.CouldntDecodeError:
            raise CouldNotDecode

        if relative:
            path = os.getcwd() + conversion_folder + mp3name
        else:
            path = conversion_folder + mp3name

        # Check if extras was ticked by checking if dictionary key was set.
        if song.artist is not None:
            if not song.thumb:
                converted_song.export(path, format="mp3", tags={"artist": song.artist.strip(), "title":
                            song.title.strip()})
            else:
                converted_song.export(path, format="mp3", cover=song.thumb, tags={"artist": song.artist.strip(),
                            "title": song.title.strip()})
        else:
            song.export(path, format="mp3")
        self.last_converted = song.title.strip()
        return path

    def combine_video_and_audio(self, video_path, audio_path, conversion_folder="\\MP4s\\", relative=True):
        pass


class Downloader:
    def __init__(self):
        pass

    def download_cover(self, thumb, downloadfolder, relative):
        """Downloads a thumbnail for the song from the YouTube thumbnail."""
        # Changes folder path if relative or not.
        if relative:
            downloadfolder = os.getcwd() + downloadfolder
        # Use requests to download the image.
        img_data = requests.get(thumb).content
        # Download it to a specific folder with a specific name.
        with open((downloadfolder + "cover.jpeg"), 'wb') as handler:
            handler.write(img_data)
        # Return download location.
        return (downloadfolder + "cover.jpeg")

    def download_audio(self, videoURL, downloadfolder="\\tempDownload\\", relative=True, extra=True):
        """Downloads the audio from the YouTube video as a .webm file."""
        song = Song
        try:
            video = pytube.YouTube(videoURL)
        except pytube.exceptions.RegexMatchError:
            raise InvalidURL
        # 251 is the iTag for the highest quality audio.
        audiostream = video.streams.get_by_itag(251)

        # TODO: make a regex for this bit cause its kinda ridiculous.
        # Download video.
        if relative:
            song.path = os.getcwd() + downloadfolder + audiostream.title.replace(",", "").replace(".", "").replace("'", "").replace("|", "").replace("/", "").replace("\"", "") + ".webm"
            audiostream.download(os.getcwd() + downloadfolder)
        else:
            song.path = downloadfolder + audiostream.title.replace(",", "").replace(".", "").replace("'", "").replace("|", "").replace("/", "").replace("\"", "") + ".webm"
            audiostream.download(downloadfolder)

        # Add extra information to dictionary to be assigned by converter.
        if extra:
            # Split the string into 2 by finding the first instance of ' - '.
            if " - " in video.title:
                song.artist = video.title.split(" - ", 1)[0]
                song.title = video.title.split(" - ", 1)[1]
            else:
                song.artist = video.title
                song.title = video.title
            try:
                song.thumb = self.download_cover(video.thumbnail_url, downloadfolder, relative)
            except pytube.exceptions.RegexMatchError or KeyError["assets"]:
                song.thumb = None
        return song

    def download_video(self, videoURL, download_folder="\\tempDownload\\", relative=True, extra=True):
        """Downloads the video from the YouTube."""
        song = Song
        try:
            video = pytube.YouTube(videoURL)
        except pytube.exceptions.RegexMatchError:
            raise InvalidURL
        
        # Download video.
        video_stream = video.streams.get_by_itag(137)

        # 251 is the iTag for the highest quality audio.
        audiostream = video.streams.get_by_itag(251)

        # TODO: download video and audio, convert audio to mp3, combine video and audio, and then move to plex.

        # Combine audio and video.
        ffmpeg.concat(video_stream, audiostream, v=1, a=1).output('./processed_folder/finished_video.mp4').run()

    def get_playlist(self, playlistURL, startingindex: int = None, endingindex: int = None):
        """Downloads all songs in a playlist as a .webm file."""
        # Variables
        playlistURLs = []
        playlistVideos = pytube.Playlist(playlistURL)

        # Error checking for indexes.
        if endingindex is None:
            endingindex = len(playlistVideos)
        if endingindex > len(playlistVideos):
            endingindex = len(playlistVideos)
        if startingindex is None:
            startingindex = 0
        if startingindex < 0:
            startingindex = 0
        if startingindex > endingindex:
            startingindex = endingindex - 1

        # Creates a list of YouTube URLS from the playlist.
        for url in playlistVideos.video_urls[startingindex:endingindex]:
            playlistURLs.append(url)

        return playlistURLs


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.downloader = Downloader()
        self.converter = Converter()

    @commands.command(name="download")
    async def download_command(self, ctx, song: str):
        """Downloads a song from YouTube."""
        LocalPathCheck.path_exists(download_music_folder, True)
        LocalPathCheck.path_exists(music_conversion_folder, True)

        file = discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
        await ctx.send(file=file, content=file.filename)

        LocalPathCheck.clear_local_cache(download_music_folder, True)
        await asyncio.sleep(60)
        LocalPathCheck.clear_local_cache(music_conversion_folder, True)

    @download_command.error
    async def download_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name="playlist")
    async def download_playlist_command(self, ctx, playlist):
        """Downloads a playlist of songs from YouTube."""
        LocalPathCheck.path_exists(download_music_folder, True)
        LocalPathCheck.path_exists(music_conversion_folder, True)

        playlist_urls = self.downloader.get_playlist(playlist)

        for song in playlist_urls:
            file = discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
            await ctx.send(file=file, content=file.filename)
            await asyncio.sleep(3)
            LocalPathCheck.clear_local_cache(download_music_folder, True)
            LocalPathCheck.clear_local_cache(music_conversion_folder, True)

        await ctx.send("Finished downloading playlist.")

    @download_playlist_command.error
    async def download_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")


    @commands.command(name="download_plex")
    async def download_plex_command(self, ctx, song):
        """Downloads a song from Youtube and converts it to MP3 and places it onto Plex."""
        LocalPathCheck.path_exists(download_music_folder, True)
        LocalPathCheck.path_exists(plex_music_folder, True)

        self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), plex_music_folder)

        await asyncio.sleep(3)
        LocalPathCheck.clear_local_cache(download_music_folder, True)
        # TODO: add a check to see if the file is there and if not, send an error message.
        # TODO: move file to plex media server.
        ctx.send(f"Downloaded {self.converter.last_converted} to plex server.")

    @download_plex_command.error
    async def download_plex_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    
    @commands.command(name="download_playlist_plex")
    async def download_playlist_plex_command(self, ctx, playlist):
        """Downloads a playlist of songs from Youtube and converts it to MP3 and places it onto Plex."""
        LocalPathCheck.path_exists(download_music_folder, True)
        LocalPathCheck.path_exists(plex_music_folder, True)

        playlist_urls = self.downloader.get_playlist(playlist)

        for song in playlist_urls:
            file = discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
            await ctx.send(file=file, content=file.filename)
            await asyncio.sleep(3)
            LocalPathCheck.clear_local_cache(download_music_folder, True)
        
        await ctx.send("Finished downloading playlist to plex server.")

    @download_playlist_plex_command.error
    async def download_playlist_plex_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name="download_video_plex")
    async def download_video_command(self, ctx, video):
        """Downloads a video from Youtube and places it onto Plex."""
        LocalPathCheck.path_exists(download_video_folder, True)
        LocalPathCheck.path_exists(plex_video_folder, True)

        self.downloader.download_video(video, download_video_folder)
        await asyncio.sleep(3)
        LocalPathCheck.clear_local_cache(download_music_folder, True)

    @download_video_command.error
    async def download_playlist_plex_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")


def setup(bot):
    bot.add_cog(Download(bot))
