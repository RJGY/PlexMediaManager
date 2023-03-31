# Plex Media Manager
## A python bot which converts YouTube videos to MP3s and sends the raw MP3 file to the user. Can also play music through Discord. 

## Usage
^!download {url} {channel} - Downloads the song to the requested channel. If the channel does not exist, it will create a new channel of the requested name. If the song already exists, an error will pop up saying that the song has already been downloaded with a link to the song.
^!playlist {url} {channel} [starting index] [ending index] - Downloads the playlist to the requested channel. If the channel does not exist, it will create a new channel of the requested name. Starting index indicates where to start downloading the playlist from (inclusive). Ending index indicates where to stop downloading the playlist from (exclusive).
^!list {channel} - Lists all songs downloaded in the discord channel.
^!play c {channel} [starting index] [ending index] - Plays songs from discord channel.
^!play {youtube url} - Plays song from youtube.
^!playlist {youtube url} - Plays playlist from youtube.

## Coming Soon
- Webscraping torrent websites
- Downloading torrents to qbittorrent with magnet links
- Moving torrented files to plex folders on completion and random media checks

## Requirements
Java 13+ (Java 17 recommended)
Python 3.10
Lavalink 3.7.5
Pip + Every package in requirements.txt


## How to run cause im a fucking idiot and i always forget how to operate this shit
1. run lavalink server 
2. run main.py
3. invite the bot to ur server
4. run commands

## Limitations
- Playing a playlist only does up to 320 songs.


- REALLY NEED A LOGGER BRO,.....

## TODO Music
- Autoplay still doesnt work for some reason BECAUSE IT ONLY WORKS FOR SPOTIFY... LMFAOOOOOOOOO SO COOL DONT WRITE THAT IN THE DOCUMENTATION GUYS???? LIKE WTF????

## TODO Download
- Need to delete files which are uploaded to discord/drive
- Create list of songs downloaded and location in discord so no duplicates by saving to txt file
- add ytsearch query to downloading songs

## TODO Torrent
- Scan media on server and check whats there. then make sure not to download duplicates.
- Bot webscraper.
- Download torrents from magnet links which we torrent.
- local file google drive sync in folder
- remove waits in the thingo
