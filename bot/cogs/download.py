# Standard library imports
import asyncio
import json
import logging
import os
import shutil
from typing import Any, Callable, Union

# Third-party imports
import discord
from discord import app_commands # Added
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
# Ensure global path variables are absolute
download_music_folder = os.path.abspath(os.getenv("DOWNLOAD_MUSIC_FOLDER", ""))
music_conversion_folder = os.path.abspath(os.getenv("MUSIC_CONVERSION_FOLDER", ""))
download_video_folder = os.path.abspath(os.getenv("DOWNLOAD_VIDEO_FOLDER", ""))
video_conversion_folder = os.path.abspath(os.getenv("VIDEO_CONVERSION_FOLDER", ""))
plex_video_folder = os.path.abspath(os.getenv("PLEX_VIDEO_FOLDER", ""))
plex_music_folder = os.path.abspath(os.getenv("PLEX_MUSIC_FOLDER", ""))
temp_spotify_folder = os.path.abspath(os.getenv("TEMP_SPOTIFY_FOLDER", ""))

# These are IDs or other settings, not local file paths, so abspath is not needed.
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

    def upload_video(self, video_path):
        """Uploads a video to Google Drive. Expects an absolute path to the video file."""
        # The video_path parameter is now expected to be an absolute path to the file.
        # The GoogleDriveFile title should probably be just the filename, not the whole path.
        file_title = os.path.basename(video_path)
        file1 = self.drive.CreateFile({'title': file_title, 'parents': [{'id': google_drive_video_upload}]})
        file1.SetContentFile(video_path) # video_path is already absolute
        file1.Upload() # Upload file.
        self.last_video_upload = file_title # Store filename
        
    def upload_music(self, music_path):
        """Uploads music to Google Drive. Expects an absolute path to the music file."""
        # The music_path parameter is now expected to be an absolute path to the file.
        file_title = os.path.basename(music_path)
        file1 = self.drive.CreateFile({'title': file_title, 'parents': [{'id': google_drive_music_upload}]})
        file1.SetContentFile(music_path) # music_path is already absolute
        file1.Upload() # Upload file.
        self.last_music_upload = file_title # Store filename
        

class LocalPathCheck:
    def __init__(self):
        pass
    # This function checks if the path exists. If it does not, it will create a directory there.
    # If the function cannot execute properly, it will exit.
    def path_exists(self, dir_path):
        """Checks if the path exists. If it does not, it will create a directory there. Expects an absolute path."""
        # dir_path is already absolute
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
    def clear_local_cache(self, dir_path):
        """Clears the directory of all files within temporary cache directory. Expects an absolute path."""
        # dir_path is already absolute
        for file_name in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    # This function checks the size of the directory and all files under it.
    # If the size of it is greater than one gigabyte, it will return true. else false.
    def check_cache(self, dir_path):
        """Checks the size of the directory and all files under it. If the size of it is greater than one gigabyte, it will return true. else false. Expects an absolute path."""
        # dir_path is already absolute
        size = 0
        for folderpath, _, filenames in os.walk(dir_path):
            for file in filenames:
                path = os.path.join(folderpath, file)
                size += os.path.getsize(path)
        # Return true or false depending on whether the size of the files are greater than 1 gigabyte.
        return size > 1000000000

    def clear_all_temp_caches(self):
        """Clears all caches of temporary files. Assumes global folder paths are absolute."""
        # Assumes download_music_folder and download_video_folder are absolute paths
        for file_name in os.listdir(download_music_folder):
            file_path = os.path.join(download_music_folder, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        for file_name in os.listdir(download_video_folder):
            file_path = os.path.join(download_video_folder, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    def clear_all_converted_caches(self):
        """Clears all caches of converted files. Assumes global folder paths are absolute."""
        # Assumes music_conversion_folder and video_conversion_folder are absolute paths
        for file_name in os.listdir(music_conversion_folder):
            file_path = os.path.join(music_conversion_folder, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        for file_name in os.listdir(video_conversion_folder):
            file_path = os.path.join(video_conversion_folder, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    def move_video_to_plex(self, media_path):
        '''Move the video to the plex video server. Expects an absolute media_path.'''
        # media_path is already absolute. plex_video_folder must also be absolute.
        shutil.move(media_path, plex_video_folder)

    def move_music_to_plex(self, media_path):
        '''Move the music to the plex music server. Expects an absolute media_path.'''
        # media_path is already absolute. plex_music_folder must also be absolute.
        shutil.move(media_path, plex_music_folder)

    def check_size_for_discord(self, media_path):
        """Checks the size of the media file. If its larger than 8mb, it will return false else true. Expects an absolute media_path."""
        # media_path is already absolute
        size = os.path.getsize(media_path)
        # If size is greater than 8mbs, return true. else false.
        return size > 8000000 # 8MB
    
    def clear_temp_spotify(self, folder_path):
        """Clears the specified folder of files. Assumes folder_path is absolute."""
        # folder_path is an absolute path
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
    def get_temp_spotify_file(self, folder_path):
        """Gets a file from the specified folder. Assumes folder_path is absolute."""
        # folder_path is an absolute path
        for file_name in os.listdir(folder_path):
            # Returns the first file found. Consider if this is always the desired behavior.
            return os.path.join(folder_path, file_name)
        return None # Return None if no file is found
        

class Converter:
    def __init__(self):
        self.last_converted = ""

    # This function converts any media file to an mp3.
    def convert_to_mp3(self, song: Song, output_folder): # Removed relative, default path
        """Converts a song from .webm to mp3. output_folder is an absolute path."""
        # Error checking in case downloader runs into an error.
        if not isinstance(song, Song):
            raise IncorrectArgumentType

        # Error checking in case the path doesnt exist inside the dictionary
        if not song.path: # song.path should be absolute if set by downloader
            raise MissingArgument

        video_file = song.path # Assumed absolute
        mp3_name = song.youtube_name.replace("|","-").replace("\""," ").replace(":", " ").replace("/","") + ".mp3"

        # output_folder is now an absolute path
        path = os.path.join(output_folder, mp3_name)
            
        # Assuming download_music_folder is an absolute path global variable
        # The first argument to crop_thumbnail (song.thumbnail) is a path, should be absolute
        # The second argument (output_folder for crop_thumbnail) also needs to be absolute.
        # If cropped thumbnail is temporary, its output folder should be handled carefully.
        # For now, let's assume download_music_folder is the place for temporary cropped images.
        if song.thumbnail: # song.thumbnail path should be absolute
            song.thumbnail = self.crop_thumbnail(song.thumbnail, download_music_folder) # download_music_folder must be absolute

        # Check if extras was ticked by checking if dictionary key was set.
        if song.artist is not None:
            if song.thumbnail: # song.thumbnail is now an absolute path
                subprocess.call(["ffmpeg", "-y", "-i", video_file,"-i", song.thumbnail, "-metadata", "artist=" + song.artist.strip(), "-metadata", "title=" + song.title.strip(), 
                                 "-map", "0:a", "-map", "1:0", "-c:1", "copy", "-b:a", "320k", "-ar", "48000", "-y", "-id3v2_version", "3", path])
            else:
                subprocess.call(["ffmpeg", "-y", "-i", video_file, "-metadata", "artist=" + song.artist.strip(), "-metadata", "title=" + song.title.strip(), 
                                 "-b:a", "320k", "-ar", "48000", "-y", path])
        else:
            subprocess.call(["ffmpeg", "-y", "-i", video_file, "-metadata", "title=" + song.title.strip(), 
                                 "-b:a", "320k", "-ar", "48000", "-y", path])
        self.last_converted = mp3_name # This should be just the name, not the full path.
        return path # Returns absolute path

    def combine_video_and_audio(self, video: Video, output_folder): # Removed relative, default path
        """Combines a video and audio file into a mp4. output_folder is an absolute path."""
        # if not isinstance(video, Video):
        #     raise IncorrectArgumentType

        if not video.audio_path: # Assumed absolute
            raise MissingArgument

        if not video.video_path: # Assumed absolute
            raise MissingArgument

        # output_folder is now an absolute path
        output_file_path = os.path.join(output_folder, video.title + ".mp4")

        # Combine audio and video.
        subprocess.call(["ffmpeg", "-y", "-i", video.video_path, "-i", video.audio_path, "-c:v", "copy", output_file_path])

        self.last_converted = video.title + ".mp4" # This should be just the name.
        video.path = output_file_path # video.path is now absolute
        return video.path # Returns absolute path

    def crop_thumbnail(self, thumbnail_path, output_folder): # Removed relative, default path
        """Crops the thumbnail from the YouTube video. thumbnail_path and output_folder are absolute paths."""
        img = Image.open(thumbnail_path) # thumbnail_path is absolute
        
        width, height = img.width, img.height
        
        # print(width, height) # Consider removing debug prints
        
        ratio = width / height
        
        # print(ratio) # Consider removing debug prints
        
        # output_folder is now an absolute path
        output_thumbnail_path = os.path.join(output_folder, "new_cover.jpeg")

        if ratio > 1:
            # width is bigger
            unit = width / 16
            new_height = 9 * unit
            diff = (height - new_height) / 2
            crop_call = "crop={}:{}:0:{}".format(int(width), int(new_height), int(diff))
            subprocess.call(["ffmpeg", "-y", "-i", thumbnail_path, "-vf", crop_call, "-c:a", "copy", output_thumbnail_path])
        else:
            # width is smaller
            unit = height / 9
            new_width = 16 * unit
            diff = (width - new_width) / 2
            crop_call = "crop={}:{}:{}:0".format(int(new_width), int(height), int(diff))
            subprocess.call(["ffmpeg", "-y", "-i", thumbnail_path, "-vf", crop_call, "-c:a", "copy", output_thumbnail_path])

        return output_thumbnail_path # Returns absolute path

class Downloader:
    def __init__(self):
        self.last_downloaded = "" # This should store just filename, not path

    def download_cover(self, thumb_url, download_folder): # Removed relative, default path
        """Downloads a thumbnail for the song from the YouTube thumbnail. download_folder is an absolute path."""
        # download_folder is now an absolute path
        output_path = os.path.join(download_folder, "cover.jpeg")
        # Use requests to download the image.
        img_data = requests.get(thumb_url).content
        # Download it to a specific folder with a specific name.
        with open(output_path, 'wb') as handler:
            handler.write(img_data)
        # Return download location.
        return output_path # Returns absolute path

    def download_audio(self, videoURL, download_folder, extra = True): # Removed relative, default path
        """Downloads the audio from the YouTube video. download_folder is an absolute path."""
        song = Song()
        try:
            video = pytubefix.YouTube(videoURL)
        except pytubefix.exceptions.RegexMatchError:
            raise InvalidURL
        # 251 is the iTag for the highest quality audio.
        audio_stream = video.streams.get_audio_only()

        # download_folder is now an absolute path
        song.path = os.path.join(download_folder, "audio.mp3")
        audio_stream.download(output_path=download_folder, filename="audio.mp3")

        song.youtube_name = video.title # This is the video title, not filename

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
                song.artist = video.title # Fallback if no separator
                song.title = video.title
            try:
                # download_folder must be absolute for download_cover
                song.thumbnail = self.download_cover(video.thumbnail_url, download_folder)
            except RegexMatchError or KeyError: # Fixed KeyError syntax
                song.thumbnail = None
        return song

    def download_video(self, videoURL, download_folder): # Removed relative, default path
        """Downloads the video from the YouTube. download_folder is an absolute path."""
        mp4 = Video() # Instantiate class
        try:
            video = pytubefix.YouTube(videoURL)
        except RegexMatchError:
            raise InvalidURL
        
        # Download video.
        video_stream = video.streams.get_by_itag(313) # Prefer 313 itag

        resolution_pointer = 0 # Corrected typo

        #TODO: check if video_stream exists, if not, download next highest quality video.
        while video_stream is None and resolution_pointer < len(resolutions):
            video_stream = video.streams.get_by_itag(resolutions[resolution_pointer])
            resolution_pointer += 1

        if video_stream is None:
            raise NoVideoStream

        # 251 is the iTag for the highest quality audio.
        audio_stream = video.streams.get_by_itag(251)

        mp4.youtube_name = video.title # This is the video title

        # download_folder is now an absolute path
        mp4.video_path = os.path.join(download_folder, "video.mp4")
        mp4.audio_path = os.path.join(download_folder, "audio.webm")

        audio_stream.download(output_path=download_folder, filename="audio.webm")
        video_stream.download(output_path=download_folder, filename="video.mp4")

        # Title of video (used as part of filename later in converter)
        mp4.title = video.title.replace("|","").replace("\"","").replace(":", "").replace("/", "")

        # Return video.
        self.last_downloaded = mp4.title # Store the YouTube title, not filename/path
        return mp4

    def get_playlist(self, playlistURL, startingindex: int = None, endingindex: int = None):
        """Returns a list of video URLs from a YouTube playlist."""
        # Variables
        playlist_urls = [] # Corrected variable name
        playlist_videos = pytubefix.Playlist(playlistURL) # Corrected variable name

        # Error checking for indexes.
        if endingindex is None:
            endingindex = len(playlist_videos)
        if endingindex > len(playlist_videos): # Ensure endingindex is not out of bounds
            endingindex = len(playlist_videos)
        if startingindex is None:
            startingindex = 0
        if startingindex < 0: # Ensure startingindex is not negative
            startingindex = 0
        if startingindex > endingindex: # Ensure start is not after end
            startingindex = endingindex # or perhaps raise an error / handle differently

        # Creates a list of YouTube URLS from the playlist.
        # Slicing handles empty list if start >= end
        for url in playlist_videos.video_urls[startingindex:endingindex]:
            playlist_urls.append(url)

        return playlist_urls
    
    def download_spotify(self, url, output_folder): # Removed relative
        """Downloads a song from a Spotify URL. output_folder is an absolute path."""
        # output_folder is now an absolute path
        # No longer need: output_folder = os.path.join(os.getcwd(), output_folder)

        current_path = os.getcwd() # Store current working directory
        os.chdir(output_folder) # Change to target directory for spotdl
        try:
            subprocess.run(["spotdl", url], check=True) # Added check=True for error handling
        except subprocess.CalledProcessError as e:
            print(f"Spotdl error: {e}") # Or handle more gracefully
            # Potentially re-raise or return an error status
        finally:
            os.chdir(current_path) # Always change back to original directory


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

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for app commands in this cog."""
        error_message = f"An unexpected error occurred: {error}"
        ephemeral = True

        custom_errors = (InvalidURL, NoVideoStream, IncorrectArgumentType, MissingArgument, CouldNotDecode)
        original_error = getattr(error, 'original', error)

        if isinstance(original_error, custom_errors):
            error_message = str(original_error)

        logging.error(f"Error in Download cog, command {interaction.command.name if interaction.command else 'Unknown'}: {original_error}", exc_info=error)

        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=ephemeral)
        else:
            try:
                await interaction.response.send_message(error_message, ephemeral=ephemeral)
            except discord.errors.InteractionResponded:
                 await interaction.followup.send(error_message, ephemeral=ephemeral)
            except Exception as e:
                logging.error(f"Failed to send error message for Download cog: {e}")

    @app_commands.command(name="download", description="Downloads a song from YouTube.")
    @app_commands.describe(song_url="The YouTube URL of the song to download.")
    async def download_command(self, interaction: discord.Interaction, song_url: str):
        await interaction.response.defer()

        # Determine download and conversion paths
        current_download_folder = download_music_folder
        current_conversion_folder = music_conversion_folder

        self.path_check.path_exists(current_download_folder)
        if current_download_folder != current_conversion_folder: # Only create if different to avoid error
            self.path_check.path_exists(current_conversion_folder)

        downloaded_song_obj = self.downloader.download_audio(song_url, current_download_folder)
        # Pass the determined conversion folder to convert_to_mp3
        converted_song_path = self.converter.convert_to_mp3(downloaded_song_obj, current_conversion_folder)

        if not self.path_check.check_size_for_discord(converted_song_path):
            await interaction.followup.send(file=discord.File(converted_song_path), content=os.path.basename(converted_song_path))
        else:
            # Ensure upload_music gets the correct path if conversion path differs from download
            await self.uploader.upload_music(converted_song_path) # This is blocking, consider to_thread
            await interaction.followup.send(f"Uploaded {os.path.basename(converted_song_path)} to Google Drive as it was too large for Discord.")

        # Clear the specific download folder used for this operation
        self.path_check.clear_local_cache(current_download_folder)
        # If conversion folder is different and also temporary, clear it too.
        # For now, assuming if location is provided, it's persistent or managed by user outside this clear.
        # If current_download_folder and current_conversion_folder are derived from the default temporary folders
        # and are different, then clear current_conversion_folder as well if it's temporary.
        # This part needs careful consideration of what "location" implies for cleanup.
        # If 'location' is a custom user path, we probably shouldn't clear it automatically.
        # If 'location' is just a subfolder of the default temp, then it should be cleared.
        # The current logic clears current_download_folder. If current_conversion_folder is different AND temporary, it should also be cleared.
        # For simplicity, if location is provided, we are assuming it's a more permanent user-defined path, so we only clear the specific download_folder.
        # If no location is provided, default download_music_folder is cleared.
        # If location IS provided, current_download_folder (which might be an absolute custom path or a subpath of default) is cleared.
        # This seems fine: we always clear where the initial download happened. The converted file is either sent or uploaded.

    @app_commands.command(name="playlist", description="Downloads a playlist of songs from YouTube.")
    @app_commands.describe(playlist_url="The YouTube URL of the playlist to download.")
    async def download_playlist_command(self, interaction: discord.Interaction, playlist_url: str):
        await interaction.response.defer()

        current_download_folder = download_music_folder
        current_conversion_folder = music_conversion_folder

        self.path_check.path_exists(current_download_folder)
        if current_download_folder != current_conversion_folder:
            self.path_check.path_exists(current_conversion_folder)

        playlist_urls = self.downloader.get_playlist(playlist_url)
        if not playlist_urls:
            await interaction.followup.send("Could not retrieve playlist or playlist is empty.")
            return

        await interaction.followup.send(f"Found {len(playlist_urls)} songs in playlist.")
        for item_url in playlist_urls:
            try:
                # Download to the determined download folder
                downloaded_song_obj = self.downloader.download_audio(item_url, current_download_folder)
                # Convert in the determined conversion folder
                converted_song_path = self.converter.convert_to_mp3(downloaded_song_obj, current_conversion_folder)

                if not self.path_check.check_size_for_discord(converted_song_path):
                    await interaction.followup.send(file=discord.File(converted_song_path), content=os.path.basename(converted_song_path))
                else:
                    await self.uploader.upload_music(converted_song_path) # Blocking
                    await interaction.followup.send(f"Uploaded {os.path.basename(converted_song_path)} to Google Drive (too large).")

                # Clear the specific download folder used for this item
                # If using a custom location, this will clear that custom location after each song.
                # This might not be desired if the custom location is meant to be persistent.
                # Consider clearing only if it's a subfolder of the default temp, or not clearing at all if location is set.
                # For now, maintaining consistency with single download: clear the folder where download happened.
                self.path_check.clear_local_cache(current_download_folder)
                # If current_conversion_folder is different and temporary, it should also be cleared.
                # As with single download, if 'location' is custom, we assume user manages it.
                # If no location, default download_music_folder is cleared (which is current_download_folder).
            except Exception as e:
                await interaction.followup.send(f"Error downloading song {item_url}: {e}")
            await asyncio.sleep(1)
        await interaction.followup.send("Finished downloading playlist.")

    @app_commands.command(name="download_plex", description="Downloads a song from YouTube to Plex.")
    @app_commands.describe(song_url="The YouTube URL of the song for Plex.")
    @app_commands.describe(location="Optional subfolder within Plex music library.")
    async def download_plex_command(self, interaction: discord.Interaction, song_url: str, location: str = None):
        await interaction.response.defer()

        plex_target_folder = plex_music_folder
        if location:
            if os.path.isabs(location):
                # If absolute, use it directly. This might be useful for mounting different Plex libraries or specific drives.
                plex_target_folder = location
            else:
                # If relative, join with the default Plex music folder.
                plex_target_folder = os.path.join(plex_music_folder, location)

        await interaction.followup.send(f"Starting download of {song_url} to Plex server at '{plex_target_folder}'.")

        # Ensure the temporary download folder exists
        self.path_check.path_exists(download_music_folder)
        # Ensure the final Plex target folder exists
        self.path_check.path_exists(plex_target_folder)

        # Initial download always goes to the temporary download_music_folder
        downloaded_song_obj = self.downloader.download_audio(song_url, download_music_folder)
        # Conversion output goes to the determined plex_target_folder
        converted_song_path = self.converter.convert_to_mp3(downloaded_song_obj, plex_target_folder)

        # Clear the temporary download folder
        self.path_check.clear_local_cache(download_music_folder)
        await interaction.followup.send(f"Downloaded {os.path.basename(converted_song_path)} to Plex server at {plex_target_folder}.")

    @app_commands.command(name="download_playlist_plex", description="Downloads a YouTube playlist to Plex.")
    @app_commands.describe(playlist_url="The YouTube URL of the playlist for Plex.")
    @app_commands.describe(location="Optional subfolder within Plex music library for the playlist.")
    async def download_playlist_plex_command(self, interaction: discord.Interaction, playlist_url: str, location: str = None):
        await interaction.response.defer()

        plex_target_folder = plex_music_folder
        if location:
            if os.path.isabs(location):
                plex_target_folder = location
            else:
                plex_target_folder = os.path.join(plex_music_folder, location)

        await interaction.followup.send(f"Starting download of playlist {playlist_url} to Plex server at '{plex_target_folder}'.")

        # Ensure the temporary download folder exists
        self.path_check.path_exists(download_music_folder)
        # Ensure the final Plex target folder for the playlist exists
        self.path_check.path_exists(plex_target_folder)

        playlist_urls = self.downloader.get_playlist(playlist_url)
        if not playlist_urls:
            await interaction.followup.send("Could not retrieve playlist or playlist is empty.")
            return

        await interaction.followup.send(f"Found {len(playlist_urls)} songs. Downloading to Plex at '{plex_target_folder}'...")
        for item_url in playlist_urls:
            try:
                # Initial download always goes to the temporary download_music_folder
                downloaded_song_obj = self.downloader.download_audio(item_url, download_music_folder)
                # Conversion output goes to the determined plex_target_folder for the playlist
                converted_song_path = self.converter.convert_to_mp3(downloaded_song_obj, plex_target_folder)
                await interaction.followup.send(f"Downloaded {os.path.basename(converted_song_path)} to Plex at {plex_target_folder}.")
                # Clear the temporary download folder after each song
                self.path_check.clear_local_cache(download_music_folder)
            except Exception as e:
                await interaction.followup.send(f"Error downloading song {item_url} to Plex: {e}")
            await asyncio.sleep(1)
        await interaction.followup.send(f"Finished downloading playlist to Plex server at {plex_target_folder}.")

    @app_commands.command(name="download_video_plex", description="Downloads a YouTube video to Plex.")
    @app_commands.describe(video_url="The YouTube URL of the video for Plex.")
    @app_commands.describe(location="Optional subfolder within Plex video library.")
    async def download_video_plex_command(self, interaction: discord.Interaction, video_url: str, location: str = None):
        await interaction.response.defer()

        plex_target_folder = plex_video_folder
        if location:
            if os.path.isabs(location):
                plex_target_folder = location
            else:
                plex_target_folder = os.path.join(plex_video_folder, location)

        await interaction.followup.send(f"Starting video download of {video_url} to Plex server at '{plex_target_folder}'.")

        # Ensure the temporary download folder for video components exists
        self.path_check.path_exists(download_video_folder)
        # Ensure the final Plex target folder exists
        self.path_check.path_exists(plex_target_folder)

        # Initial download of video components always goes to the temporary download_video_folder
        downloaded_video_obj = self.downloader.download_video(video_url, download_video_folder)
        # Combination and output of the final video goes to the determined plex_target_folder
        converted_video_path = self.converter.combine_video_and_audio(downloaded_video_obj, plex_target_folder)

        # Clear the temporary download folder for video components
        self.path_check.clear_local_cache(download_video_folder)
        await interaction.followup.send(f"Finished downloading {os.path.basename(converted_video_path)} to Plex server at {plex_target_folder}.")

    @app_commands.command(name="download_video_playlist_plex", description="Downloads a YouTube video playlist to Plex.")
    @app_commands.describe(playlist_url="The YouTube URL of the video playlist for Plex.")
    @app_commands.describe(location="Optional subfolder within Plex video library for the playlist.")
    async def download_video_playlist_plex_command(self, interaction: discord.Interaction, playlist_url: str, location: str = None):
        await interaction.response.defer()

        plex_target_folder = plex_video_folder
        if location:
            if os.path.isabs(location):
                plex_target_folder = location
            else:
                plex_target_folder = os.path.join(plex_video_folder, location)

        await interaction.followup.send(f"Starting video playlist download of {playlist_url} to Plex server at '{plex_target_folder}'.")

        # Ensure the temporary download folder for video components exists
        self.path_check.path_exists(download_video_folder)
        # Ensure the final Plex target folder for the playlist exists
        self.path_check.path_exists(plex_target_folder)

        playlist_urls = self.downloader.get_playlist(playlist_url)
        if not playlist_urls:
            await interaction.followup.send("Could not retrieve playlist or playlist is empty.")
            return

        await interaction.followup.send(f"Found {len(playlist_urls)} videos. Downloading to Plex at '{plex_target_folder}'...")
        for item_url in playlist_urls:
            try:
                # Initial download of video components always goes to the temporary download_video_folder
                downloaded_video_obj = self.downloader.download_video(item_url, download_video_folder)
                # Combination and output of the final video goes to the determined plex_target_folder
                converted_video_path = self.converter.combine_video_and_audio(downloaded_video_obj, plex_target_folder)
                await interaction.followup.send(f"Downloaded {os.path.basename(converted_video_path)} to Plex at {plex_target_folder}.")
                # Clear the temporary download folder for video components after each video
                self.path_check.clear_local_cache(download_video_folder)
            except Exception as e:
                await interaction.followup.send(f"Error downloading video {item_url} to Plex: {e}")
            await asyncio.sleep(1)
        await interaction.followup.send(f"Finished downloading video playlist to Plex server at {plex_target_folder}.")

    @app_commands.command(name="download_spotify", description="Downloads a song from a Spotify URL.")
    @app_commands.describe(url="The Spotify URL of the song.")
    async def download_spotify_command(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        target_folder = temp_spotify_folder

        self.path_check.path_exists(target_folder)
        await interaction.followup.send(f"Downloading {url} to '{target_folder}'...")

        # Pass the determined target_folder to download_spotify
        await asyncio.to_thread(self.downloader.download_spotify, url, target_folder)

        # Pass the target_folder to get_temp_spotify_file
        spotify_file_path = await asyncio.to_thread(self.path_check.get_temp_spotify_file, target_folder)

        if spotify_file_path and os.path.exists(spotify_file_path):
            await interaction.followup.send(file=discord.File(spotify_file_path), content=os.path.basename(spotify_file_path))
        else:
            await interaction.followup.send(f"Could not find downloaded Spotify song in '{target_folder}'.")

        # Pass the target_folder to clear_temp_spotify
        await asyncio.to_thread(self.path_check.clear_temp_spotify, target_folder)

    @app_commands.command(name="download_spotify_plex", description="Downloads a Spotify song to Plex.")
    @app_commands.describe(url="The Spotify URL for Plex download.")
    @app_commands.describe(location="Optional subfolder within Plex music library.")
    async def download_spotify_plex_command(self, interaction: discord.Interaction, url: str, location: str = None):
        await interaction.response.defer()

        plex_target_folder = plex_music_folder
        if location:
            if os.path.isabs(location):
                plex_target_folder = location
            else:
                plex_target_folder = os.path.join(plex_music_folder, location)

        self.path_check.path_exists(plex_target_folder)

        await interaction.followup.send(f"Downloading {url} to Plex at '{plex_target_folder}'...")
        await asyncio.to_thread(self.downloader.download_spotify, url, plex_target_folder)
        await interaction.followup.send(f"Downloaded {url} to Plex server at '{plex_target_folder}'.")

    @app_commands.command(name="download_mix_plex", description="Downloads a YouTube mix to Plex using a mix splitter.")
    @app_commands.describe(url="The YouTube URL of the mix.")
    @app_commands.describe(location="The location/folder on Plex for the mix.")
    async def download_mix_plex_command(self, interaction: discord.Interaction, url: str, location: str):
        # This command seems to be publishing a message to Redis, not directly downloading.
        # Defer might not be strictly necessary if publish is quick, but good for consistency.
        await interaction.response.defer(ephemeral=True)
        self.mix_publisher.publish({
            "video_url": url,
            "location": location
        })
        await interaction.followup.send(f"Download request for mix {url} sent to processing queue for location {location}.", ephemeral=True)

    @app_commands.command(name="help_download", description="Displays help information for all download commands.")
    async def help_download_command(self, interaction: discord.Interaction):
        """Displays help information for all download commands."""
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Download Commands",
            description="Here's a list of available download commands:",
            color=discord.Color.blue()  # You can choose any color
        )

        for command in self.get_commands():
            if command.name == "help_download":  # Don't include the help command itself
                continue

            name = command.name

            if command.signature:
                usage = f"`{interaction.client.command_prefix}{name} {command.signature}`"
            else:
                usage = f"`{interaction.client.command_prefix}{name}`" # Fallback if signature is empty

            # Use the command's short doc or the full docstring
            description = command.short_doc or command.help or "No description available."

            embed.add_field(name=name.capitalize(), value=f"{description}\n**Usage:** {usage}", inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Download(bot))

# These test functions assume that the global path variables are absolute paths.
# If they are not, these functions would need to construct absolute paths before calling.

def e2e_music_test_without_bot_commands():
    #download
    downloader = Downloader()
    # download_audio now expects absolute path for download_music_folder
    webm_song_obj = downloader.download_audio("https://www.youtube.com/watch?v=iLo6uCGhlmU", download_music_folder)
    #convert
    converter = Converter()
    # convert_to_mp3 now expects absolute path for music_conversion_folder
    converted_path = converter.convert_to_mp3(webm_song_obj, music_conversion_folder)
    logging.info(f"E2E Test: Converted music to {converted_path}")
    #upload
    # uploader = Uploader()
    # uploader.setup()
    # uploader.upload_music(converted_path) # upload_music expects an absolute path
    # if uploader.check_if_file_exists_in_music_drive(os.path.basename(converted_path)):
    #     logging.debug("File exists in music drive.")
    # uploader.list_music_drive()
    # uploader.list_video_drive()

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_music_folder) # expects absolute path
    # path_check.clear_local_cache(music_conversion_folder) # expects absolute path

def e2e_music_playlist_test():
    #upload
    uploader = Uploader()
    uploader.setup()
    #download
    downloader = Downloader()
    for song_url in downloader.get_playlist("https://www.youtube.com/playlist?list=PLUDyUa7vgsQkzBefmiC0UbbpQIHjaI9hd"):
        webm_song_obj = downloader.download_audio(song_url, download_music_folder) # absolute path

        #convert
        converter = Converter()
        converted_path = converter.convert_to_mp3(webm_song_obj, music_conversion_folder) # absolute path
        logging.info(f"E2E Playlist Test: Converted {song_url} to {converted_path}")

        # uploader instantiated outside of for loop so it only needs to be setup once
        uploader.upload_music(converted_path) # absolute path
    # last_converted in uploader stores only filename now.
    # To check if file exists, we'd need the full path or ensure check_if_file_exists_in_music_drive uses filename.
    # For now, let's assume uploader.last_music_upload is the filename.
    if uploader.check_if_file_exists_in_music_drive(uploader.last_music_upload): # last_music_upload is filename
        logging.debug("File exists in music drive: " + uploader.last_music_upload)
    uploader.list_music_drive()
    uploader.list_video_drive()

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_music_folder) # absolute
    path_check.clear_local_cache(music_conversion_folder) # absolute

def e2e_video_test():
    downloader = Downloader()
    video_obj = downloader.download_video("https://www.youtube.com/watch?v=ajlkhFnz8eo", download_video_folder) # absolute

    converter = Converter()
    # combine_video_and_audio expects absolute path for video_conversion_folder
    converted_video_path = converter.combine_video_and_audio(video_obj, video_conversion_folder)
    logging.info(f"E2E Video Test: Converted video to {converted_video_path}")

    # uploader = Uploader()
    # uploader.setup()
    # uploader.upload_video(converted_video_path) # expects absolute path

    #clear cache
    path_check = LocalPathCheck()
    path_check.clear_local_cache(download_video_folder) # absolute
    # path_check.clear_local_cache(video_conversion_folder) # absolute
    
def download_video(): # This seems like a test function, not part of cog
    downloader = Downloader()
    converter = Converter()
    video_obj = downloader.download_video("https://www.youtube.com/watch?v=x7M8ahInYjA", download_video_folder) # absolute
    # combine_video_and_audio expects absolute path
    converted_path = converter.combine_video_and_audio(video_obj, video_conversion_folder)
    logging.info(f"Test download_video: Converted to {converted_path}")
    
def download_music(): # This seems like a test function
    downloader = Downloader()
    converter = Converter()
    song_obj = downloader.download_audio("https://www.youtube.com/watch?v=UaZFDa45u3Q", download_music_folder) # absolute
    # convert_to_mp3 expects absolute path
    converted_path = converter.convert_to_mp3(song_obj, music_conversion_folder)
    logging.info(f"Test download_music: Converted to {converted_path}")
    
def download_playlist(): # This seems like a test function for Spotify
    downloader = Downloader()
    # download_spotify expects absolute path for plex_music_folder
    downloader.download_spotify("https://open.spotify.com/playlist/2NCYQ11U8paAOIoBb5iLCI?si=MJNhcmdmQNakYMWse_XbXQ", plex_music_folder)
    logging.info(f"Test download_playlist (Spotify): Downloaded to {plex_music_folder}")

if __name__ == "__main__":
    # Configure logging for testing if needed
    logging.basicConfig(level=logging.INFO)
    # Example: Ensure global paths are defined here if running standalone for tests
    # CWD = os.getcwd()
    # download_music_folder = os.path.join(CWD, "temp_music_download")
    # music_conversion_folder = os.path.join(CWD, "temp_music_converted")
    # plex_music_folder = os.path.join(CWD, "temp_plex_music") # Example for testing
    # video_conversion_folder = os.path.join(CWD, "temp_video_converted")
    # download_video_folder = os.path.join(CWD, "temp_video_download")

    # Create dummy directories for testing if they don't exist
    # for p in [download_music_folder, music_conversion_folder, plex_music_folder, video_conversion_folder, download_video_folder]:
    #     if not os.path.exists(p):
    #         os.makedirs(p)

    download_music()
