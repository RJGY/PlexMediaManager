# Youtube Discord Downloader
## A python bot which converts YouTube videos to MP3s and sends the raw MP3 file to the user.

### Bio
So imagine this situation. You have a phone but no storage to hold all the music. You could get Spotify but that costs money. You could use Youtube for listening to music but that has ads. You could download it onto Google Drive or iCloud but that has storage limits and has an unintuitive UI for listening to music and is hard to access, browse and search for the correct music. 

This is where Discord comes in as our free cloud service. With Discord, you can store as many songs (under 8 megabytes) as messages you can send with a description of the song and organize songs into descriptive channels. This bot can download the song and then post the song into the server for us so that we can access it again. Discord's search function allows us to easily find songs which we have previously downloaded as it is faster than search functions of other cloud services. Finally, we can interact with Discord more easily as it just requires a message to interact with rather than a API call. That is what this is for.

## Usage
^!download {url} {channel} - Downloads the song to the requested channel. If the channel does not exist, it will create a new channel of the requested name. If the song already exists, an error will pop up saying that the song has already been downloaded with a link to the song.
^!playlist {url} {channel} [starting index] [ending index] - Downloads the playlist to the requested channel. If the channel does not exist, it will create a new channel of the requested name. Starting index indicates where to start downloading the playlist from (inclusive). Ending index indicates where to stop downloading the playlist from (exclusive).
^!list {channel} - Lists all songs downloaded in the discord channel.
^!play c {channel} [starting index] [ending index] - Plays songs from discord channel.
^!play {youtube url} - Plays song from youtube.
^!playlist {youtube url} - Plays playlist from youtube.


## TODO
- Get code from python youtube downloader
- Code python bot which responds to text commands.
- Create list of songs downloaded and location in discord so no duplicates by saving to txt file
- Connect 2 services together
- Bot should be able to play music as well.
