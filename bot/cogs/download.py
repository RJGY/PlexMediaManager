import discord
from discord.ext import commands
import os
import pytube
import requests
import pydub

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
        self.album = ""
        self.thumb = ""
        self.artist = ""
        self.path = ""
        self.is_converted = False


class LocalPathCheck:
    # This function checks if the path exists. If it does not, it will create a directory there.
    # If the function cannot execute properly, it will exit.
    def path_exists(dir_path, relative):
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
        if relative:
            dir_path = os.getcwd() + dir_path
        for file in os.listdir(dir_path):
            if os.path.isfile(dir_path + file):
                os.remove(dir_path + file)

    # This function checks the size of the directory and all files under it.
    # If the size of it is greater than one gigabyte, it will return true. else false.
    def check_cache(dir_path, relative):
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


class Converter:
    def __init__(self):
        self.path_check = LocalPathCheck()

    # This function converts any media file to an mp3.
    # This function uses pydub.
    def converttomp3(dictionary, conversionfolder="\\MP3s\\", relative=True):
        # Error checking in case downloader runs into an error.
        if not isinstance(dictionary, dict):
            raise IncorrectArgumentType

        # Error checking in case the path doesnt exist inside the dictionary
        if "path" not in dictionary:
            raise MissingArgument

        videofile = dictionary["path"]
        mp3name = os.path.splitext(os.path.basename(videofile))[0] + ".mp3"
        extension = os.path.splitext(os.path.basename(videofile))[1].replace(".", "")
        try:
            song = pydub.AudioSegment.from_file(videofile, format=extension)
        except pydub.exceptions.CouldntDecodeError:
            raise CouldNotDecode

        if relative:
            path = os.getcwd() + conversionfolder + mp3name
        else:
            path = conversionfolder + mp3name

        # Check if extras was ticked by checking if dictionary key was set.
        # TODO: Album is currently not working. Going to disable feature.
        if dictionary["artist"] is not None:
            if "thumb" not in dictionary or dictionary["thumb"] is None:
                song.export(path, format="mp3", tags={"artist": dictionary["artist"].strip(), "title":
                            dictionary["title"].strip(), "album": ""})
            else:
                song.export(path, format="mp3", cover=dictionary["thumb"], tags={"artist": dictionary["artist"].strip(),
                            "title": dictionary["title"].strip(), "album": dictionary["album"].strip()})
        else:
            song.export(path, format="mp3")
        return path


class Downloader:
    def __init__(self):
        self.path_check = LocalPathCheck()

    def download_cover(thumb, downloadfolder, relative):
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
        dict = {}
        try:
            video = pytube.YouTube(videoURL)
        except pytube.exceptions.RegexMatchError:
            raise InvalidURL
        # 251 is the iTag for the highest quality audio.
        audiostream = video.streams.get_by_itag(251)

        # TODO: make a regex for this bit cause its kinda ridiculous.
        # Download video.
        if relative:
            dict["path"] = os.getcwd() + downloadfolder + audiostream.title.replace(",", "").replace(".", "").replace("'", "").replace("|", "").replace("/", "") + ".webm"
            audiostream.download(os.getcwd() + downloadfolder)
        else:
            dict["path"] = downloadfolder + audiostream.title.replace(",", "").replace(".", "").replace("'", "").replace("|", "").replace("/", "") + ".webm"
            audiostream.download(downloadfolder)

        # Add extra information to dictionary to be assigned by converter.
        if extra:
            # Split the string into 2 by finding the first instance of ' - '.
            if " - " in video.title:
                dict["artist"] = video.title.split(" - ", 1)[0]
                dict["title"] = video.title.split(" - ", 1)[1]
            else:
                dict["artist"] = video.title
                dict["title"] = video.title
            try:
                dict["thumb"] = self.download_cover(video.thumbnail_url, downloadfolder, relative)
            except pytube.exceptions.RegexMatchError or KeyError["assets"]:
                dict["thumb"] = None
            dict["album"] = video.author
        return dict

    def get_playlist(playlistURL, startingindex: int = None, endingindex: int = None):
        print("Downloading URLS")
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
        print("Starting Download")
        for url in playlistVideos.video_urls[startingindex:endingindex]:
            playlistURLs.append(url)

        return playlistURLs


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.downloader = Downloader()
        self.converter = Converter()


def setup(bot):
    bot.add_cog(Download(bot))

    # TODO: add class specific shit like last song downloaded and last song converted.
    # TODO: use virtual environments cause ur an idiot
    # TODO: use oop to create new class to hold music data rather than a dictionary