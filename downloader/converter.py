import os
import pydub


# This function converts any media file to an mp3.
# This function uses pydub.
def converttomp3(dictionary, conversionfolder="\\MP3s\\", relative=True):
    # Error checking in case downloader runs into an error.
    if not isinstance(dictionary, dict):
        return False

    # Error checking in case the path doesnt exist inside the dictionary
    if "path" not in dictionary:
        print("Failed to find path for video. Returning.")
        return False

    videofile = dictionary["path"]
    mp3name = os.path.splitext(os.path.basename(videofile))[0] + ".mp3"
    extension = os.path.splitext(os.path.basename(videofile))[1].replace(".", "")
    try:
        song = pydub.AudioSegment.from_file(videofile, format=extension)
    except pydub.exceptions.CouldntDecodeError:
        print("Failed to decode video. Returning.")
        return False

    # Relative check.
    if relative:
        path = os.getcwd() + conversionfolder + mp3name
    else:
        path = conversionfolder + mp3name

    # Check if extras was ticked by checking if dictionary key was set.
    # Album is currently not working. Going to disable feature.
    if dictionary["artist"] is not None:
        if "thumb" not in dictionary or dictionary["thumb"] is None:
            song.export(path, format="mp3", tags={"artist": dictionary["artist"].strip(), "title":
                        dictionary["title"].strip(), "album": ""})
        else:
            song.export(path, format="mp3", cover=dictionary["thumb"], tags={"artist": dictionary["artist"].strip(),
                        "title": dictionary["title"].strip(), "album": dictionary["album"].strip()})
    else:
        song.export(path, format="mp3")
    return True


if __name__ == "__main__":
    print("You ran the wrong file.")
    print("Run main.py")