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


## How to run cause im a fucking idiot and i always forget how to operate this shit
0. run lavalink server 
1. run main.py
2. invite the bot to ur server
3. run commands

## TODO
- need to be able to play whole playlists
- add autoplay feature
- Create list of songs downloaded and location in discord so no duplicates by saving to txt file
- Scan media on server and check whats there. then make sure not to download duplicates.
- Bot webscraper.
- Download torrents from magnet links which we torrent.
- local file google drive sync in folder
- youtube autoplay for music playing
- remove waits in the thingo
- add ytsearch query to downloading songs