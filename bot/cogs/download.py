# Standard library imports
import asyncio
import json
import logging
import os
import shutil
from typing import Any, Callable, Union

# Third-party imports
import discord
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image
import pytubefix
from pytubefix.exceptions import RegexMatchError
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import redis
import requests
import subprocess

load_dotenv()
download_music_folder = os.getenv("DOWNLOAD_MUSIC_FOLDER")
music_conversion_folder = os.getenv("MUSIC_CONVERSION_FOLDER")
download_video_folder = os.getenv("DOWNLOAD_VIDEO_FOLDER")
video_conversion_folder = os.getenv("VIDEO_CONVERSION_FOLDER")
plex_video_folder = os.getenv("PLEX_VIDEO_FOLDER")
plex_music_folder = os.getenv("PLEX_MUSIC_FOLDER")
temp_spotify_folder = os.getenv("TEMP_SPOTIFY_FOLDER")

google_drive_music_upload = os.getenv("GOOGLE_DRIVE_MUSIC_UPLOAD")
google_drive_video_upload = os.getenv("GOOGLE_DRIVE_VIDEO_UPLOAD")
resolutions = [137, 22, 18]


class IncorrectArgumentType(commands.CommandError):
    pass


class MissingArgument(commands.CommandError):
    pass


class CouldNotDecode(commands.CommandError):
    pass


class InvalidURL(commands.CommandError):
    pass


class NoVideoStream(commands.CommandError):
    pass


class Song:
    def __init__(self):
        self.title = ""
        self.thumbnail = ""
        self.artist = ""
        self.path = ""
        self.youtube_name = ""


class Video:
    def __init__(self):
        self.title = ""
        self.audio_path = ""
        self.video_path = ""
        self.path = ""
        self.youtube_name = ""


class RedisPublisher:
    def __init__(self, host: str = 'localhost', port: int = 6379, channel: str = 'default_channel'):
        """Initialize Redis publisher with connection details and channel name."""
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        self.channel = channel

    def publish(self, message: Union[str, dict]) -> int:
        """
        Publish a message to the channel.
        Returns the number of subscribers that received the message.
        """
        try:
            # Convert dict to JSON string if necessary
            if isinstance(message, dict):
                message = json.dumps(message)
            
            return self.redis_client.publish(self.channel, message)
        except Exception as e:
            print(f"Error publishing message: {str(e)}")
            return 0

    def close(self):
        """Close the Redis connection."""
        self.redis_client.close()


class RedisSubscriber:
    def __init__(self, host: str = 'localhost', port: int = 6379, channel: str = 'default_channel'):
        """Initialize Redis subscriber with connection details and channel name."""
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.channel = channel

    def message_handler(self, message: dict) -> None:
        """Default message handler - can be overridden."""
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                print(f"Received message: {data}")
            except json.JSONDecodeError:
                print(f"Received raw message: {message['data']}")

    def subscribe(self, callback: Callable[[Any], None] = None) -> None:
        """Subscribe to the channel and process messages."""
        self.pubsub.subscribe(self.channel)
        
        # Use custom callback if provided, otherwise use default handler
        handler = callback if callback else self.message_handler
        
        print(f"Subscribed to channel: {self.channel}")
        try:
            for message in self.pubsub.listen():
                handler(message)
        except KeyboardInterrupt:
            print("\nUnsubscribing from channel...")
            self.pubsub.unsubscribe()
            self.redis_client.close()


class Uploader:
    def __init__(self):
        self.last_video_upload = ""
        self.last_music_upload = ""
        self.gauth = GoogleAuth()

    def setup(self):
        self.gauth.LocalWebserverAuth()
        self.drive = GoogleDrive(self.gauth)

    def check_drive_size(self, drive_type: str = "music"):
        if drive_type == "music":
            file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        else:
            file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        for file in file_list:
            logging.debug('title: %s, id: %s' % (file['title'], file['id']))

    def check_if_file_exists_in_music_drive(self, file_name):
        file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        for file in file_list:
            if file['title'] == file_name:
                return True
        return False

    def check_if_file_exists_in_video_drive(self, file_name):
        file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        for file in file_list:
            if file['title'] == file_name:
                return True
        return False

    def list_video_drive(self):
        file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        logging.debug("Files in video drive:")
        for file in file_list:
            logging.debug('title: %s, id: %s, size: %s' % (file['title'], file['id'], file['fileSize']))

    def list_music_drive(self):
        file_list = self.drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        print("Files in music drive:")
        for file in file_list:
            logging.debug('title: %s, id: %s, size: %s' % (file['title'], file['id'], file['fileSize']))

    def upload_video(self, video_path, relative: bool = True):
        file1 = self.drive.CreateFile({'title': video_path, 'parents': [{'id': google_drive_video_upload}]})  # Create GoogleDriveFile instance with title 'Hello.txt'.
        if relative:
            file1.SetContentFile(os.getcwd() + video_conversion_folder + video_path) # Set content of the file from given string.
        else:
            file1.SetContentFile(video_conversion_folder + video_path) # Set content of the file from given string.
        file1.Upload() # Upload file.
        self.last_video_upload = video_path
        
    def upload_music(self, music_path, relative: bool = True):
        file1 = self.drive.CreateFile({'title': music_path, 'parents': [{'id': google_drive_music_upload}]})  # Create GoogleDriveFile instance with title 'Hello.txt'.
        if relative:
            file1.SetContentFile(os.getcwd() + music_conversion_folder + music_path) # Set content of the file from given string.
        else:
            file1.SetContentFile(music_conversion_folder + music_path) # Set content of the file from given string.
        file1.Upload() # Upload file.
        self.last_music_upload = music_path 
        

class LocalPathCheck:
    def __init__(self):
        pass
    # This function checks if the path exists. If it does not, it will create a directory there.
    # If the function cannot execute properly, it will exit.
    def path_exists(self, dir_path, relative = True):
        """Checks if the path exists. If it does not, it will create a directory there."""
        if relative:
            dir_path = os.getcwd() + dir_path
        # If the path exists, return and continue.
        if os.path.isdir(dir_path):
            logging.debug("Path found: " + dir_path)
            return
        else:
            try:
                # If the path does not exist, make it.
                logging.debug("Creating path: " + dir_path)
                os.mkdir(dir_path)
            except OSError:
                # If error, print debug and exit.
                logging.debug("Creation of path failed. Exiting program.")
                return

    # This function clears the directory of all files, while leaving other directories.
    def clear_local_cache(self, dir_path, relative = True):
        """Clears the directory of all files within temporary cache directory."""
        if relative:
            dir_path = os.getcwd() + dir_path
        for file in os.listdir(dir_path):
            if os.path.isfile(dir_path + file):
                os.remove(dir_path + file)

    # This function checks the size of the directory and all files under it.
    # If the size of it is greater than one gigabyte, it will return true. else false.
    def check_cache(self, dir_path, relative = True):
        """Checks the size of the directory and all files under it. If the size of it is greater than one gigabyte, it will return true. else false."""
        if relative:
            dir_path = os.getcwd() + dir_path

        size = 0
        for folderpath, foldernames, filenames in os.walk(dir_path):
            for file in filenames:
                path = folderpath + file
                size += os.path.getsize(path)
        # Return true or false depending on whether the size of the files are greater than 1 gigabyte.
        return size > 1000000000

    def clear_all_temp_caches(self):
        """Clears all caches of temporary files."""
        for file in os.listdir(os.getcwd() + download_music_folder):
            if os.path.isfile(os.getcwd() + download_music_folder + file):
                os.remove(os.getcwd() + download_music_folder + file)
        
        for file in os.listdir(os.getcwd() + download_video_folder):
            if os.path.isfile(os.getcwd() + download_video_folder + file):
                os.remove(os.getcwd() + download_video_folder + file)

    def clear_all_converted_caches(self):
        """Clears all caches of converted files."""
        for file in os.listdir(os.getcwd() + music_conversion_folder):
            if os.path.isfile(os.getcwd() + music_conversion_folder + file):
                os.remove(os.getcwd() + music_conversion_folder + file)
        
        for file in os.listdir(os.getcwd() + video_conversion_folder):
            if os.path.isfile(os.getcwd() + video_conversion_folder + file):
                os.remove(os.getcwd() + video_conversion_folder + file)

    def move_video_to_plex(self, media, relative = True):
        '''Move the video to the plex video server.'''
        if relative:
            shutil.move(os.getcwd() + media, plex_video_folder)
        else:
            shutil.move(media, plex_video_folder)

    def move_music_to_plex(self, media, relative = True):
        '''Move the music to the plex music server.'''
        if relative:
            shutil.move(os.getcwd() + media, plex_music_folder)
        else: 
            shutil.move(media, plex_music_folder)

    def check_size_for_discord(self, media, relative = True):
        """Checks the size of the media file. If its larger than 8mb, it will return false else true."""
        if relative:
            size = os.path.getsize(os.getcwd() + media)
        else:
            size = os.path.getsize(media)
        
        # If size is greater than 8mbs, return true. else false.
        return size > 8000000
    
    def clear_temp_spotify(self):
        """Clears the temp spotify folder."""
        for file in os.listdir(os.getcwd() + temp_spotify_folder):
            if os.path.isfile(os.getcwd() + temp_spotify_folder + file):
                os.remove(os.getcwd() + temp_spotify_folder + file)
                
    def get_temp_spotify_file(self):
        """Gets the temp spotify folder."""
        for file in os.listdir(os.getcwd() + temp_spotify_folder):
            return file
        

class Converter:
    def __init__(self):
        self.last_converted = ""

    # This function converts any media file to an mp3.
    def convert_to_mp3(self, song: Song, output_folder = "\\MP3s\\", relative = True):
        """Converts a song from .webm to mp3."""
        # Error checking in case downloader runs into an error.
        if not isinstance(song, Song):
            raise IncorrectArgumentType

        # Error checking in case the path doesnt exist inside the dictionary
        if not song.path:
            raise MissingArgument

        video_file = song.path
        mp3_name = song.youtube_name.replace("|","-").replace("\""," ").replace(":", " ").replace("/","") + ".mp3"

        if relative:
            path = os.getcwd() + output_folder + mp3_name
        else:
            path = output_folder + mp3_name
            
        song.thumbnail = self.crop_thumbnail(song.thumbnail, download_music_folder, relative)

        # Check if extras was ticked by checking if dictionary key was set.
        if song.artist is not None:
            if song.thumbnail:
                subprocess.call(["ffmpeg", "-y", "-i", video_file,"-i", song.thumbnail, "-metadata", "artist=" + song.artist.strip(), "-metadata", "title=" + song.title.strip(), 
                                 "-map", "0:a", "-map", "1:0", "-c:1", "copy", "-b:a", "320k", "-ar", "48000", "-y", "-id3v2_version", "3", path])
            else:
                subprocess.call(["ffmpeg", "-y", "-i", video_file, "-metadata", "artist=" + song.artist.strip(), "-metadata", "title=" + song.title.strip(), 
                                 "-b:a", "320k", "-ar", "48000", "-y", path])
        else:
            subprocess.call(["ffmpeg", "-y", "-i", video_file, "-metadata", "title=" + song.title.strip(), 
                                 "-b:a", "320k", "-ar", "48000", "-y", path])
        self.last_converted = mp3_name
        return path

    def combine_video_and_audio(self, video: Video, output_folder = "\\MP4s\\", relative = True):
        """Combines a video and audio file into a mp4."""
        # if not isinstance(video, Video):
        #     raise IncorrectArgumentType

        if not video.audio_path:
            raise MissingArgument

        if not video.video_path:
            raise MissingArgument

        # Combine audio and video.
        if relative:
            subprocess.call(["ffmpeg", "-y", "-i", video.video_path, "-i", video.audio_path, "-c:v", "copy", os.getcwd() + output_folder + video.title + ".mp4"])
        else:
            subprocess.call(["ffmpeg", "-y", "-i", video.video_path, "-i", video.audio_path, "-c:v", "copy", output_folder + video.title + ".mp4"])
        self.last_converted = video.title + ".mp4"
        video.path = os.getcwd() + output_folder + video.title + ".mp4"
        return video.path

    def crop_thumbnail(self, thumbnail, output_folder = "\\temp_download\\", relative = True):
        """Crops the thumbnail from the YouTube video."""
        img = Image.open(thumbnail)
        
        width, height = img.width, img.height
        
        print(width, height)
        
        ratio = width / height
        
        print(ratio)
        
        if ratio > 1:
            # width is bigger
            unit = width / 16
            new_height = 9 * unit
            diff = (height - new_height) / 2
            crop_call = "crop={}:{}:0:{}".format(int(width), int(new_height), int(diff))
            subprocess.call(["ffmpeg", "-y", "-i", thumbnail, "-vf", crop_call, "-c:a", "copy", os.getcwd() + output_folder + "new_cover.jpeg"])
        else:
            # width is smaller
            unit = height / 9
            new_width = 16 * unit
            diff = (width - new_width) / 2
            crop_call = "crop={}:{}:{}:0".format(int(new_width), int(height), int(diff))
            subprocess.call(["ffmpeg", "-y", "-i", thumbnail, "-vf", crop_call, "-c:a", "copy", os.getcwd() + output_folder + "new_cover.jpeg"])

        return os.getcwd() + output_folder + "new_cover.jpeg"

class Downloader:
    def __init__(self):
        self.last_downloaded = ""

    def download_cover(self, thumb, downloadfolder = "\\temp_download\\", relative = True):
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

    def download_audio(self, videoURL, download_folder = "\\temp_download\\", relative = True, extra = True):
        """Downloads the audio from the YouTube video as a .webm file."""
        song = Song()
        try:
            video = pytubefix.YouTube(videoURL, 'WEB')
        except pytubefix.exceptions.RegexMatchError:
            raise InvalidURL
        # 251 is the iTag for the highest quality audio.
        audio_stream = video.streams.get_audio_only()

        # Download video.
        if relative:
            song.path = os.getcwd() + download_folder + "audio.mp3"
            audio_stream.download(os.getcwd() + download_folder, "audio.mp3")
        else:
            song.path = download_folder + "audio.mp3"
            audio_stream.download(download_folder, "audio.mp3")

        song.youtube_name = video.title

        # Add extra information to dictionary to be assigned by converter.
        if extra:
            # Split the string into 2 by finding the first instance of ' - ' or ' | '.
            # This is done because the title is in the format of 'Artist - Title'
            if " - " in video.title:
                song.artist = video.title.split(" - ", 1)[0]
                song.title = video.title.split(" - ", 1)[1]
            elif " | " in video.title:
                song.artist = video.title.split(" | ", 1)[0]
                song.title = video.title.split(" | ", 1)[1]
            else:
                song.artist = video.title
                song.title = video.title
            try:
                song.thumbnail = self.download_cover(video.thumbnail_url, download_folder, relative)
            except RegexMatchError or KeyError["assets"]:
                song.thumbnail = None
        return song

    def download_video(self, videoURL, download_folder = "\\temp_download\\", relative = True):
        """Downloads the video from the YouTube."""
        mp4 = Video
        try:
            video = pytubefix.YouTube(videoURL, 'WEB')
        except RegexMatchError:
            raise InvalidURL
        
        # Download video.
        video_stream = video.streams.get_by_itag(313)

        resoltion_pointer = 0

        #TODO: check if video_stream exists, if not, download next highest quality video.
        while video_stream is None and resoltion_pointer < len(resolutions):
            video_stream = video.streams.get_by_itag(resolutions[resoltion_pointer])
            resoltion_pointer += 1

        if video_stream is None:
            raise NoVideoStream

        # 251 is the iTag for the highest quality audio.
        audio_stream = video.streams.get_by_itag(251)

        mp4.youtube_name = video.title

        # Download video.
        if relative:
            mp4.video_path = os.getcwd() + download_folder + "video.mp4"
            mp4.audio_path = os.getcwd() + download_folder + "audio.webm"
            audio_stream.download(os.getcwd() + download_folder, "audio.webm")
            video_stream.download(os.getcwd() + download_folder, "video.mp4")
        else:
            mp4.video_path = download_folder + "video.mp4"
            mp4.audio_path = download_folder + "audio.webm"
            audio_stream.download(download_folder)
            video_stream.download(download_folder)

        # Title of video
        mp4.title = video.title.replace("|","").replace("\"","").replace(":", "").replace("/", "")

        # Return video.
        self.last_downloaded = mp4.title
        return mp4

    def get_playlist(self, playlistURL, startingindex: int = None, endingindex: int = None):
        """Downloads all songs in a playlist as a .webm file."""
        # Variables
        playlistURLs = []
        playlistVideos = pytubefix.Playlist(playlistURL)

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
    
    def download_spotify(self, url, output_folder, relative = True):
        # Downloads a song from a Spotify URL.
        if relative:
            output_folder = os.path.join(os.getcwd(), output_folder)
        old_path = os.getcwd()
        os.chdir(output_folder)
        subprocess.run(["spotdl", url])
        os.chdir(old_path)


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.downloader = Downloader()
        self.converter = Converter()
        self.path_check = LocalPathCheck()
        self.uploader = Uploader()
        self.mix_publisher = RedisPublisher(channel='mix_processing')
        self.mix_finished_subscriber = RedisSubscriber(channel='mix_processing_finished')
        self.uploader.setup()

    @commands.command(name = "download")
    async def download_command(self, ctx, song: str):
        """Downloads a song from YouTube."""
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(music_conversion_folder, True)

        file = discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
        if not self.path_check.check_size_for_discord(os.getcwd() + music_conversion_folder + self.converter.last_converted, False):
            await ctx.send(file=file, content=file.filename)
        else:
            await self.uploader.upload_music(os.getcwd() + music_conversion_folder + self.converter.last_converted)

        self.path_check.clear_local_cache(download_music_folder, True)

    @download_command.error
    async def download_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name = "playlist")
    async def download_playlist_command(self, ctx, playlist):
        """Downloads a playlist of songs from YouTube."""
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(music_conversion_folder, True)

        playlist_urls = self.downloader.get_playlist(playlist)

        for song in playlist_urls:
            file = discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
            await ctx.send(file=file, content=file.filename)
            await asyncio.sleep(3)
            self.path_check.clear_local_cache(download_music_folder, True)

        await ctx.send("Finished downloading playlist.")

    @download_playlist_command.error
    async def download_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")


    @commands.command(name = "download_plex")
    async def download_plex_command(self, ctx, song):
        """Downloads a song from Youtube and converts it to MP3 and places it onto Plex."""
        await ctx.send(f"Starting download to plex server.")
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(plex_music_folder, False)

        self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), plex_music_folder, False)

        await asyncio.sleep(3)
        self.path_check.clear_local_cache(download_music_folder, True)
        await ctx.send(f"Downloaded {self.converter.last_converted} to plex server.")

    @download_plex_command.error
    async def download_plex_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    
    @commands.command(name="download_playlist_plex")
    async def download_playlist_plex_command(self, ctx, playlist):
        """Downloads a playlist of songs from Youtube and converts it to MP3 and places it onto Plex."""
        await ctx.send(f"Starting download to plex server.")
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(plex_music_folder, True)

        playlist_urls = self.downloader.get_playlist(playlist)

        for song in playlist_urls:
            file = await discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), plex_music_folder, False))
            await ctx.send(file = file, content = file.filename)
            await asyncio.sleep(3)
            self.path_check.clear_local_cache(download_music_folder, True)
        
        await ctx.send("Finished downloading playlist to plex server.")

    @download_playlist_plex_command.error
    async def download_playlist_plex_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name = "download_video_plex")
    async def download_video_command(self, ctx, video):
        """Downloads a video from Youtube and uploads it to Plex."""
        await ctx.send(f"Starting download to plex server.")
        self.path_check.path_exists(download_video_folder, True)
        self.path_check.path_exists(plex_video_folder, True)

        self.converter.combine_video_and_audio(self.downloader.download_video(video, download_video_folder), plex_video_folder, False)
        self.path_check.clear_local_cache(download_video_folder, True)
        await ctx.send(f"Finished downloading {self.downloader.last_downloaded} to plex server.")

    @download_video_command.error
    async def download_video_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name = "download_video_playlist_plex")
    async def download_video_playlist_command(self, ctx, playlist):
        """Downloads a playlist of videos from Youtube and uploads them to Plex."""
        await ctx.send(f"Starting download to plex server.")
        self.path_check.path_exists(download_video_folder, True)
        self.path_check.path_exists(plex_video_folder, True)

        playlist_urls = await self.downloader.get_playlist(playlist)

        for video in playlist_urls:
            self.converter.combine_video_and_audio(self.downloader.download_video(video, download_video_folder), plex_video_folder, False)
            # this needs to be fixed
            await asyncio.sleep(3)
            self.path_check.clear_local_cache(download_video_folder, True)
        await ctx.send("Finished downloading playlist to plex server.")

    @download_video_playlist_command.error
    async def download_video_playlist_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")
            
    @commands.command(name = "download_spotify", aliases = ["ds"])
    async def download_spotify_command(self, ctx, url):
        """Downloads a song from a Spotify URL."""
        self.path_check.path_exists(temp_spotify_folder, True)
        await ctx.send(f"Downloading {url}...")
        self.downloader.download_spotify(url, temp_spotify_folder, True)
        file = await discord.File(self.path_check.get_temp_spotify_file())
        ctx.send(file=file, content=file.filename)
        await asyncio.sleep(3)
        self.path_check.clear_temp_spotify()
        
        
    @commands.command(name = "download_spotify_plex", aliases = ["dsp"])
    async def download_spotify_plex_command(self, ctx, url):
        """Downloads a song from a Spotify URL to plex."""
        await ctx.send(f"Downloading {url}...")
        await asyncio.to_thread(self.downloader.download_spotify, url, plex_music_folder, False)
        await ctx.send(f"Downloaded {url} to plex server.")


    @commands.command(name="download_mix_plex", aliases = ["dmp"])
    async def download_mix_plex_command(self, ctx, url):
        """Downloads a mix from Youtube via URL to plex with youtube mix splitter."""
        self.mix_publisher.publish({
            "video_url": url
        })
        await ctx.send(f"Downloading {url} as mix...")


async def setup(bot):
    await bot.add_cog(Download(bot))

def e2e_music_test_without_bot_commands():
    #download
    downloader = Downloader()
    webm_song = downloader.download_audio("https://www.youtube.com/watch?v=iLo6uCGhlmU", download_music_folder)
    #convert
    converter = Converter()
    converter.convert_to_mp3(webm_song, music_conversion_folder)
    #upload
    # uploader = Uploader()
    # uploader.setup()
    # uploader.upload_music(converter.last_converted)
    # if uploader.check_if_file_exists_in_music_drive(converter.last_converted):
    #     logging.debug("File exists in music drive.")
    # uploader.list_music_drive()
    # uploader.list_video_drive()

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_music_folder)
    # path_check.clear_local_cache(music_conversion_folder)

def e2e_music_playlist_test():
    #upload
    uploader = Uploader()
    uploader.setup()
    #download
    downloader = Downloader()
    for song in downloader.get_playlist("https://www.youtube.com/playlist?list=PLUDyUa7vgsQkzBefmiC0UbbpQIHjaI9hd"):
        webm_song = downloader.download_audio(song, download_music_folder)

        #convert
        converter = Converter()
        converter.convert_to_mp3(webm_song, music_conversion_folder)

        # uploader instantiated outside of for loop so it only needs to be setup once
        uploader.upload_music(converter.last_converted)
    if uploader.check_if_file_exists_in_music_drive(converter.last_converted):
        logging.debug("File exists in music drive: " + converter.last_converted)
    uploader.list_music_drive()
    uploader.list_video_drive()

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_music_folder)
    path_check.clear_local_cache(music_conversion_folder)

def e2e_video_test():
    downloader = Downloader()
    webm_video = downloader.download_video("https://www.youtube.com/watch?v=ajlkhFnz8eo", download_video_folder)

    converter = Converter()
    converter.combine_video_and_audio(webm_video, video_conversion_folder, True)

    # uploader = Uploader()
    # uploader.setup()
    # uploader.upload_video(converter.last_converted)

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_video_folder)
    # path_check.clear_local_cache(video_conversion_folder)
    
def download_video():
    downloader = Downloader()
    converter = Converter()
    webm_video = downloader.download_video("https://www.youtube.com/watch?v=x7M8ahInYjA", download_video_folder)
    converter.combine_video_and_audio(webm_video, video_conversion_folder, True)
    
def download_music():
    downloader = Downloader()
    converter = Converter()
    webm_song = downloader.download_audio("https://www.youtube.com/watch?v=-fCtvurGDD8", download_music_folder)
    converter.convert_to_mp3(webm_song, music_conversion_folder, True)
    
def download_playlist():
    downloader = Downloader()
    downloader.download_spotify("https://open.spotify.com/playlist/2NCYQ11U8paAOIoBb5iLCI?si=MJNhcmdmQNakYMWse_XbXQ", plex_music_folder, True)

if __name__ == "__main__":
    download_playlist()
