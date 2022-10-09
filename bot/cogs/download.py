import discord
from discord.ext import commands
import os
import pytube
import requests
import pydub
import asyncio
import ffmpeg
import shutil
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


download_music_folder = "\\temp_music\\"
music_conversion_folder = "\\mp3\\"
download_video_folder = "\\temp_video\\"
video_conversion_folder = "\\mp4\\"
plex_video_folder = "\\plex_video_server\\"
plex_music_folder = "\\plex_music_server\\"


google_drive_music_upload = "1msuMdUVM1yfn29I4c4dat_qxwE0ukdrY"
google_drive_video_upload = "1_GStfEVLlIA6V6ooCfrv4mGKndf6mKTT"


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


class Video:
    def __init__(self):
        self.title = ""
        self.audio_path = ""
        self.video_path = ""
        self.path = ""


class Uploader:
    def __init__(self):
        self.last_video_upload = ""
        self.last_music_upload = ""
        self.gauth = GoogleAuth()

    def setup(self):
        self.gauth.LocalWebserverAuth()

    def check_drive_size(self, drive_type: str = "music"):
        drive = GoogleDrive(self.gauth)
        if drive_type == "music":
            file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        else:
            file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        for file in file_list:
            print('title: %s, id: %s' % (file['title'], file['id']))

    def check_if_file_exists_in_music_drive(self, file_name):
        drive = GoogleDrive(self.gauth)
        file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        for file in file_list:
            if file['title'] == file_name:
                return True
        return False

    def check_if_file_exists_in_video_drive(self, file_name):
        drive = GoogleDrive(self.gauth)
        file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        for file in file_list:
            if file['title'] == file_name:
                return True
        return False

    def list_video_drive(self):
        drive = GoogleDrive(self.gauth)
        file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_video_upload)}).GetList()
        print("Files in video drive:")
        for file in file_list:
            print('title: %s, id: %s, size: %s' % (file['title'], file['id'], file['fileSize']))

    def list_music_drive(self):
        drive = GoogleDrive(self.gauth)
        file_list = drive.ListFile({'q': "'{}' in parents and trashed=false".format(google_drive_music_upload)}).GetList()
        print("Files in music drive:")
        for file in file_list:
            print('title: %s, id: %s, size: %s' % (file['title'], file['id'], file['fileSize']))

    def upload_video(self, video_path, relative: bool = True):
        drive = GoogleDrive(self.gauth)
        file1 = drive.CreateFile({'title': video_path, 'parents': [{'id': google_drive_video_upload}]})  # Create GoogleDriveFile instance with title 'Hello.txt'.
        if relative:
            file1.SetContentString(os.getcwd() + video_conversion_folder + video_path) # Set content of the file from given string.
        else:
            file1.SetContentString(video_conversion_folder + video_path) # Set content of the file from given string.
        file1.Upload() # Upload file.
        self.last_video_upload = video_path
        
    def upload_music(self, music_path, relative: bool = True):
        drive = GoogleDrive(self.gauth)
        file1 = drive.CreateFile({'title': music_path, 'parents': [{'id': google_drive_music_upload}]})  # Create GoogleDriveFile instance with title 'Hello.txt'.
        if relative:
            file1.SetContentString(os.getcwd() + music_conversion_folder + music_path) # Set content of the file from given string.
        else:
            file1.SetContentString(music_conversion_folder + music_path) # Set content of the file from given string.
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

    def clear_all_caches(self):
        """Clears all caches of temporary files."""
        for file in os.listdir(os.getcwd() + download_music_folder):
            if os.path.isfile(os.getcwd() + download_music_folder + file):
                os.remove(os.getcwd() + download_music_folder + file)
        
        for file in os.listdir(os.getcwd() + download_video_folder):
            if os.path.isfile(os.getcwd() + download_video_folder + file):
                os.remove(os.getcwd() + download_video_folder + file)

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
        
        # If size is greater than 8mbs, return false. else true.
        return size > 8000000
        

class Converter:
    def __init__(self):
        self.last_converted = ""

    # This function converts any media file to an mp3.
    # This function uses pydub.
    def convert_to_mp3(self, song: Song, output_folder = "\\MP3s\\", relative = True):
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
            converted_song = pydub.AudioSegment.from_file(videofile, format = extension)
        except pydub.exceptions.CouldntDecodeError:
            raise CouldNotDecode

        if relative:
            path = os.getcwd() + output_folder + mp3name
        else:
            path = output_folder + mp3name

        # Check if extras was ticked by checking if dictionary key was set.
        if song.artist is not None:
            if not song.thumb:
                converted_song.export(path, format = "mp3", tags = {"artist": song.artist.strip(), "title":
                            song.title.strip()})
            else:
                converted_song.export(path, format = "mp3", cover = song.thumb, tags = {"artist": song.artist.strip(),
                            "title": song.title.strip()})
        else:
            song.export(path, format = "mp3")
        self.last_converted = song.title.strip()
        return path

    def combine_video_and_audio(self, video: Video, output_folder = "\\MP4s\\"):
        """Combines a video and audio file into a mp4."""
        # if not isinstance(video, Video):
        #     raise IncorrectArgumentType

        if not video.audio_path:
            raise MissingArgument

        if not video.video_path:
            raise MissingArgument

        # Function must always be relative. Absolute paths are only allowed here so we get current working directory.
        # Combine audio and video.
        ffmpeg.concat(ffmpeg.input(video.video_path), ffmpeg.input(video.audio_path), v = 1, a = 1).output(os.getcwd() + output_folder + video.title + ".mp4").run()
        self.last_converted = video.title
        video.path = os.getcwd() + output_folder + video.title + ".mp4"
        return video.path


class Downloader:
    def __init__(self):
        self.last_downloaded = ""

    def download_cover(self, thumb, downloadfolder = "\\tempDownload\\", relative = True):
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

    def download_audio(self, videoURL, downloadfolder = "\\tempDownload\\", relative = True, extra = True):
        """Downloads the audio from the YouTube video as a .webm file."""
        song = Song
        try:
            video = pytube.YouTube(videoURL)
        except pytube.exceptions.RegexMatchError:
            raise InvalidURL
        # 251 is the iTag for the highest quality audio.
        audiostream = video.streams.get_by_itag(251)

        # Download video.
        if relative:
            song.path = os.getcwd() + downloadfolder + "audio.webm"
            audiostream.download(os.getcwd() + downloadfolder, "audio.webm")
        else:
            song.path = downloadfolder + "audio.webm"
            audiostream.download(downloadfolder, "audio.webm")

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

    def download_video(self, videoURL, download_folder = "\\tempDownload\\", relative = True):
        """Downloads the video from the YouTube."""
        mp4 = Video
        try:
            video = pytube.YouTube(videoURL)
        except pytube.exceptions.RegexMatchError:
            raise InvalidURL
        
        # Download video.
        video_stream = video.streams.get_by_itag(137)

        #TODO: check if video_stream exists, if not, download next highest quality video.

        # 251 is the iTag for the highest quality audio.
        audio_stream = video.streams.get_by_itag(251)

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
        mp4.title = video.title

        # Return video.
        self.last_downloaded = mp4.title
        return mp4

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
        self.path_check = LocalPathCheck()
        self.uploader = Uploader()

    @commands.command(name = "download")
    async def download_command(self, ctx, song: str):
        """Downloads a song from YouTube."""
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(music_conversion_folder, True)

        file = await discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), music_conversion_folder))
        await ctx.send(file=file, content=file.filename)

        self.path_check.clear_local_cache(download_music_folder, True)
        await asyncio.sleep(60)

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
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(plex_music_folder, True)

        self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), plex_music_folder)

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
        self.path_check.path_exists(download_music_folder, True)
        self.path_check.path_exists(plex_music_folder, True)

        playlist_urls = self.downloader.get_playlist(playlist)

        for song in playlist_urls:
            file = await discord.File(self.converter.convert_to_mp3(self.downloader.download_audio(song, download_music_folder), plex_music_folder))
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
        self.path_check.path_exists(download_video_folder, True)
        self.path_check.path_exists(plex_video_folder, True)

        self.converter.combine_video_and_audio(self.downloader.download_video(video, download_video_folder), plex_video_folder)
        self.path_check.clear_local_cache(download_video_folder, True)
        await ctx.send(f"Finished downloading {self.downloader.last_downloaded} to plex server.")

    @download_video_command.error
    async def download_video_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")

    @commands.command(name = "download_video_playlist_plex")
    async def download_video_playlist_command(self, ctx, playlist):
        """Downloads a playlist of videos from Youtube and uploads them to Plex."""
        self.path_check.path_exists(download_video_folder, True)
        self.path_check.path_exists(plex_video_folder, True)

        playlist_urls = await self.downloader.get_playlist(playlist)

        for video in playlist_urls:
            self.converter.combine_video_and_audio(self.downloader.download_video(video, download_video_folder), plex_video_folder)
            await asyncio.sleep(3)
            self.path_check.clear_local_cache(download_video_folder, True)
        await ctx.send("Finished downloading playlist to plex server.")

    @download_video_playlist_command.error
    async def download_video_playlist_command_error(self, ctx, exc):
        if isinstance(exc, InvalidURL):
            await ctx.send("YouTube URL was not valid.")


def setup(bot):
    bot.add_cog(Download(bot))

if __name__ == "__main__":
    uploader = Uploader()
    uploader.setup()
    uploader.upload_video("lol2.mp3")
    uploader.upload_music("carolesdaughter - Creep.mp3")
    if uploader.check_if_file_exists_in_video_drive("lol.mp3"):
        print("File exists in video drive.")
    if uploader.check_if_file_exists_in_music_drive("lol2.mp3"):
        print("File exists in music drive.")
    uploader.list_music_drive()
    uploader.list_video_drive()