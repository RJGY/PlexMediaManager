import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call
import asyncio

# Make sure bot.cogs.download is importable.
# This might require adjusting PYTHONPATH or how tests are run.
# For now, assuming it's directly importable.
from bot.cogs.download import Download, Song
from bot.cogs.download import download_music_folder, music_conversion_folder, plex_music_folder, temp_spotify_folder, download_video_folder, plex_video_folder

# Dummy Song object for mocking
dummy_song_obj = Song()
dummy_song_obj.path = "dummy/path/to/song.mp3"
dummy_song_obj.title = "Dummy Title"
dummy_song_obj.artist = "Dummy Artist"
dummy_song_obj.thumbnail = "dummy/path/to/thumb.jpg"
dummy_song_obj.youtube_name = "Dummy YouTube Name"


class TestDownloadCog(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Mock the bot instance
        self.mock_bot = MagicMock()

        # Instantiate the Cog with the mocked bot
        self.cog = Download(self.mock_bot)

        # Mock interaction object
        self.mock_interaction = MagicMock()
        self.mock_interaction.response = AsyncMock()
        self.mock_interaction.followup = AsyncMock()

        # Mock helper classes attached to the cog instance
        self.cog.downloader = MagicMock()
        self.cog.converter = MagicMock()
        self.cog.path_check = MagicMock()
        self.cog.uploader = MagicMock()
        self.cog.mix_publisher = MagicMock() # Added as it's in __init__
        self.cog.mix_finished_subscriber = MagicMock() # Added as it's in __init__

        # Set default return values for methods that are called
        # and whose return values are used by the command logic
        self.cog.downloader.download_audio.return_value = dummy_song_obj
        self.cog.converter.convert_to_mp3.return_value = "/dummy/converted/song.mp3"
        self.cog.path_check.check_size_for_discord.return_value = False # Assume file is not too large for Discord
        self.cog.path_check.get_temp_spotify_file.return_value = "/dummy/spotify/song.mp3"


    async def test_download_command_location_none(self):
        """Test download_command with location=None."""
        song_url = "test_url"

        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=None)

        # Check interaction responses
        self.mock_interaction.response.defer.assert_called_once()

        # Check path_exists calls
        expected_path_exists_calls = [
            call(download_music_folder),
            call(music_conversion_folder)
        ]
        self.cog.path_check.path_exists.assert_has_calls(expected_path_exists_calls, any_order=True)

        # Check downloader call
        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)

        # Check converter call
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, music_conversion_folder)

        # Check discord file sending (or upload)
        self.cog.path_check.check_size_for_discord.assert_called_once_with("/dummy/converted/song.mp3")
        # Assuming file is small enough for direct send
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


        # Check cache clearing
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

    async def test_download_command_location_absolute(self):
        """Test download_command with an absolute path for location."""
        song_url = "test_url_abs"
        abs_location = "/custom/abs/path"

        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_location, "song.mp3")

        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=abs_location)

        self.mock_interaction.response.defer.assert_called_once()

        # Path_exists should be called for the absolute path.
        # Since current_download_folder and current_conversion_folder are the same, it's called once.
        self.cog.path_check.path_exists.assert_called_once_with(abs_location)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, abs_location)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, abs_location)

        self.cog.path_check.check_size_for_discord.assert_called_once_with(os.path.join(abs_location, "song.mp3"))
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

        self.cog.path_check.clear_local_cache.assert_called_once_with(abs_location)

    async def test_download_command_location_relative(self):
        """Test download_command with a relative path for location."""
        song_url = "test_url_rel"
        rel_location = "my_songs"

        expected_download_path = os.path.join(download_music_folder, rel_location)
        expected_conversion_path = os.path.join(music_conversion_folder, rel_location)

        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_conversion_path, "song.mp3")

        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=rel_location)

        self.mock_interaction.response.defer.assert_called_once()

        expected_path_calls = [
            call(expected_download_path),
            call(expected_conversion_path)
        ]
        self.cog.path_check.path_exists.assert_has_calls(expected_path_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, expected_download_path)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, expected_conversion_path)

        self.cog.path_check.check_size_for_discord.assert_called_once_with(os.path.join(expected_conversion_path, "song.mp3"))
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

        self.cog.path_check.clear_local_cache.assert_called_once_with(expected_download_path)

    # Tests for download_playlist_command
    async def test_download_playlist_command_location_none(self):
        """Test download_playlist_command with location=None."""
        playlist_url = "test_playlist_url"
        dummy_urls = ["url1", "url2"]
        self.cog.downloader.get_playlist.return_value = dummy_urls

        # Reset mocks that are called multiple times in a loop or sequence
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock() # Reset to check followup calls accurately per test

        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        # Initial path_exists calls
        initial_path_exists_calls = [call(download_music_folder), call(music_conversion_folder)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        # Check calls within the loop
        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)
        self.assertEqual(self.cog.downloader.download_audio.call_count, len(dummy_urls))

        convert_to_mp3_calls = [call(dummy_song_obj, music_conversion_folder) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)
        self.assertEqual(self.cog.converter.convert_to_mp3.call_count, len(dummy_urls))

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)
        self.assertEqual(self.cog.path_check.clear_local_cache.call_count, len(dummy_urls))

        # Check one of the followup sends for file (others are status messages)
        # This assumes the converted_song_path is "/dummy/converted/song.mp3" for each
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


    async def test_download_playlist_command_location_absolute(self):
        """Test download_playlist_command with an absolute path for location."""
        playlist_url = "test_playlist_url_abs"
        abs_location = "/custom/abs/playlist/path"
        dummy_urls = ["url1", "url2"]
        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_location, "song.mp3") # Make path consistent

        # Reset mocks
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.cog.path_check.path_exists.reset_mock() # Reset this too for specific check
        self.mock_interaction.followup.send.reset_mock()


        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=abs_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        # path_exists called once for the abs_location (as download and convert paths are the same)
        self.cog.path_check.path_exists.assert_called_once_with(abs_location)

        download_audio_calls = [call(url, abs_location) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, abs_location) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(abs_location) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


    async def test_download_playlist_command_location_relative(self):
        """Test download_playlist_command with a relative path for location."""
        playlist_url = "test_playlist_url_rel"
        rel_location = "my_playlist_downloads"
        dummy_urls = ["url1", "url2"]
        self.cog.downloader.get_playlist.return_value = dummy_urls

        expected_download_path = os.path.join(download_music_folder, rel_location)
        expected_conversion_path = os.path.join(music_conversion_folder, rel_location)
        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_conversion_path, "song.mp3")


        # Reset mocks
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.cog.path_check.path_exists.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=rel_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(expected_download_path), call(expected_conversion_path)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, expected_download_path) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, expected_conversion_path) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(expected_download_path) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

    # Tests for download_plex_command
    async def test_download_plex_command_location_none(self):
        """Test download_plex_command with location=None."""
        song_url = "test_plex_url_none"
        # Reset relevant mocks to ensure clean state for this test
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        # Expected path for the converted song for followup message content
        self.cog.converter.convert_to_mp3.return_value = os.path.join(plex_music_folder, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(plex_music_folder)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, plex_music_folder)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        # Check that the followup message contains the correct path
        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {plex_music_folder}."
        )

    async def test_download_plex_command_location_absolute(self):
        """Test download_plex_command with an absolute path for location."""
        song_url = "test_plex_url_abs"
        abs_plex_location = "/custom/plex/abs/path"
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_plex_location, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=abs_plex_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(abs_plex_location)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, abs_plex_location)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {abs_plex_location}."
        )

    async def test_download_plex_command_location_relative(self):
        """Test download_plex_command with a relative path for location."""
        song_url = "test_plex_url_rel"
        rel_plex_location = "my_plex_songs"
        expected_plex_path = os.path.join(plex_music_folder, rel_plex_location)

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_plex_path, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=rel_plex_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(expected_plex_path)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, expected_plex_path)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {expected_plex_path}."
        )

    # Tests for download_playlist_plex_command
    async def test_download_playlist_plex_command_location_none(self):
        """Test download_playlist_plex_command with location=None."""
        playlist_url = "test_plex_playlist_url_none"
        dummy_urls = ["url1", "url2"]

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(plex_music_folder, "song.mp3")

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(plex_music_folder)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)
        self.assertEqual(self.cog.downloader.download_audio.call_count, len(dummy_urls))

        convert_to_mp3_calls = [call(dummy_song_obj, plex_music_folder) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)
        self.assertEqual(self.cog.converter.convert_to_mp3.call_count, len(dummy_urls))

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)
        self.assertEqual(self.cog.path_check.clear_local_cache.call_count, len(dummy_urls))

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {plex_music_folder}."
        )

    async def test_download_playlist_plex_command_location_absolute(self):
        """Test download_playlist_plex_command with an absolute path for location."""
        playlist_url = "test_plex_playlist_url_abs"
        abs_plex_location = "/custom/plex/abs/playlist/path"
        dummy_urls = ["url1", "url2"]

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_plex_location, "song.mp3")

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=abs_plex_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(abs_plex_location)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, abs_plex_location) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {abs_plex_location}."
        )

    async def test_download_playlist_plex_command_location_relative(self):
        """Test download_playlist_plex_command with a relative path for location."""
        playlist_url = "test_plex_playlist_url_rel"
        rel_plex_location = "my_plex_playlist"
        expected_plex_path = os.path.join(plex_music_folder, rel_plex_location)
        dummy_urls = ["url1", "url2"]

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_plex_path, "song.mp3")

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()

        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=rel_plex_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(expected_plex_path)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, expected_plex_path) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {expected_plex_path}."
        )

# Dummy Video object for mocking
dummy_video_obj = MagicMock() # Using MagicMock to simplify, can be a real Video object too
dummy_video_obj.audio_path = "dummy/video/audio.mp4"
dummy_video_obj.video_path = "dummy/video/video.mp4"
dummy_video_obj.title = "Dummy Video Title"
dummy_video_obj.youtube_name = "Dummy Video YouTube Name"
dummy_video_obj.path = "" # Will be set by combine_video_and_audio mock normally


class TestDownloadCog(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Mock the bot instance
        self.mock_bot = MagicMock()

        # Instantiate the Cog with the mocked bot
        self.cog = Download(self.mock_bot)

        # Mock interaction object
        self.mock_interaction = MagicMock()
        self.mock_interaction.response = AsyncMock()
        self.mock_interaction.followup = AsyncMock()

        # Mock helper classes attached to the cog instance
        self.cog.downloader = MagicMock()
        self.cog.converter = MagicMock()
        self.cog.path_check = MagicMock()
        self.cog.uploader = MagicMock()
        self.cog.mix_publisher = MagicMock()
        self.cog.mix_finished_subscriber = MagicMock()

        # Set default return values for methods that are called
        # and whose return values are used by the command logic
        self.cog.downloader.download_audio.return_value = dummy_song_obj
        self.cog.converter.convert_to_mp3.return_value = "/dummy/converted/song.mp3"
        self.cog.path_check.check_size_for_discord.return_value = False
        self.cog.path_check.get_temp_spotify_file.return_value = "/dummy/spotify/song.mp3"

        # For video commands
        self.cog.downloader.download_video.return_value = dummy_video_obj
        self.cog.converter.combine_video_and_audio.return_value = "/dummy/converted/video.mp4"


    async def test_download_command_location_none(self):
        """Test download_command with location=None."""
        song_url = "test_url"

        # Reset mocks for this specific test if needed (especially if run in a suite)
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.path_check.check_size_for_discord.reset_mock()

        # Redefine return value for this specific test context if it was changed elsewhere
        self.cog.converter.convert_to_mp3.return_value = "/dummy/converted/song.mp3"


        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=None)

        # Check interaction responses
        self.mock_interaction.response.defer.assert_called_once()

        # Check path_exists calls
        expected_path_exists_calls = [
            call(download_music_folder),
            call(music_conversion_folder)
        ]
        self.cog.path_check.path_exists.assert_has_calls(expected_path_exists_calls, any_order=True)

        # Check downloader call
        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)

        # Check converter call
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, music_conversion_folder)

        # Check discord file sending (or upload)
        self.cog.path_check.check_size_for_discord.assert_called_once_with("/dummy/converted/song.mp3")
        # Assuming file is small enough for direct send
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


        # Check cache clearing
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

    async def test_download_command_location_absolute(self):
        """Test download_command with an absolute path for location."""
        song_url = "test_url_abs"
        abs_location = "/custom/abs/path"

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.path_check.check_size_for_discord.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_location, "song.mp3")

        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=abs_location)

        self.mock_interaction.response.defer.assert_called_once()

        self.cog.path_check.path_exists.assert_called_once_with(abs_location)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, abs_location)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, abs_location)

        self.cog.path_check.check_size_for_discord.assert_called_once_with(os.path.join(abs_location, "song.mp3"))
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

        self.cog.path_check.clear_local_cache.assert_called_once_with(abs_location)

    async def test_download_command_location_relative(self):
        """Test download_command with a relative path for location."""
        song_url = "test_url_rel"
        rel_location = "my_songs"

        expected_download_path = os.path.join(download_music_folder, rel_location)
        expected_conversion_path = os.path.join(music_conversion_folder, rel_location)

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.path_check.check_size_for_discord.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_conversion_path, "song.mp3")

        await self.cog.download_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=rel_location)

        self.mock_interaction.response.defer.assert_called_once()

        expected_path_calls = [
            call(expected_download_path),
            call(expected_conversion_path)
        ]
        self.cog.path_check.path_exists.assert_has_calls(expected_path_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, expected_download_path)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, expected_conversion_path)

        self.cog.path_check.check_size_for_discord.assert_called_once_with(os.path.join(expected_conversion_path, "song.mp3"))
        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

        self.cog.path_check.clear_local_cache.assert_called_once_with(expected_download_path)

    # Tests for download_playlist_command
    async def test_download_playlist_command_location_none(self):
        """Test download_playlist_command with location=None."""
        playlist_url = "test_playlist_url"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()


        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = "/dummy/converted/song.mp3" # Generic path for song.mp3

        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(music_conversion_folder)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)
        self.assertEqual(self.cog.downloader.download_audio.call_count, len(dummy_urls))

        convert_to_mp3_calls = [call(dummy_song_obj, music_conversion_folder) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)
        self.assertEqual(self.cog.converter.convert_to_mp3.call_count, len(dummy_urls))

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)
        self.assertEqual(self.cog.path_check.clear_local_cache.call_count, len(dummy_urls))

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


    async def test_download_playlist_command_location_absolute(self):
        """Test download_playlist_command with an absolute path for location."""
        playlist_url = "test_playlist_url_abs"
        abs_location = "/custom/abs/playlist/path"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_location, "song.mp3")

        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=abs_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        self.cog.path_check.path_exists.assert_called_once_with(abs_location)

        download_audio_calls = [call(url, abs_location) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, abs_location) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(abs_location) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")


    async def test_download_playlist_command_location_relative(self):
        """Test download_playlist_command with a relative path for location."""
        playlist_url = "test_playlist_url_rel"
        rel_location = "my_playlist_downloads"
        dummy_urls = ["url1", "url2"]

        expected_download_path = os.path.join(download_music_folder, rel_location)
        expected_conversion_path = os.path.join(music_conversion_folder, rel_location)

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_conversion_path, "song.mp3")

        await self.cog.download_playlist_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=rel_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(expected_download_path), call(expected_conversion_path)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, expected_download_path) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, expected_conversion_path) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(expected_download_path) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")

    # Tests for download_plex_command
    async def test_download_plex_command_location_none(self):
        """Test download_plex_command with location=None."""
        song_url = "test_plex_url_none"

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(plex_music_folder, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(plex_music_folder)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, plex_music_folder)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {plex_music_folder}."
        )

    async def test_download_plex_command_location_absolute(self):
        """Test download_plex_command with an absolute path for location."""
        song_url = "test_plex_url_abs"
        abs_plex_location = "/custom/plex/abs/path"

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_plex_location, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=abs_plex_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(abs_plex_location)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, abs_plex_location)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {abs_plex_location}."
        )

    async def test_download_plex_command_location_relative(self):
        """Test download_plex_command with a relative path for location."""
        song_url = "test_plex_url_rel"
        rel_plex_location = "my_plex_songs"
        expected_plex_path = os.path.join(plex_music_folder, rel_plex_location)

        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_plex_path, "song.mp3")

        await self.cog.download_plex_command.callback(self.cog, self.mock_interaction, song_url=song_url, location=rel_plex_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_music_folder), call(expected_plex_path)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_audio.assert_called_once_with(song_url, download_music_folder)
        self.cog.converter.convert_to_mp3.assert_called_once_with(dummy_song_obj, expected_plex_path)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_music_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex server at {expected_plex_path}."
        )

    # Tests for download_playlist_plex_command
    async def test_download_playlist_plex_command_location_none(self):
        """Test download_playlist_plex_command with location=None."""
        playlist_url = "test_plex_playlist_url_none"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(plex_music_folder, "song.mp3")


        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(plex_music_folder)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)
        self.assertEqual(self.cog.downloader.download_audio.call_count, len(dummy_urls))

        convert_to_mp3_calls = [call(dummy_song_obj, plex_music_folder) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)
        self.assertEqual(self.cog.converter.convert_to_mp3.call_count, len(dummy_urls))

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)
        self.assertEqual(self.cog.path_check.clear_local_cache.call_count, len(dummy_urls))

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {plex_music_folder}."
        )

    async def test_download_playlist_plex_command_location_absolute(self):
        """Test download_playlist_plex_command with an absolute path for location."""
        playlist_url = "test_plex_playlist_url_abs"
        abs_plex_location = "/custom/plex/abs/playlist/path"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(abs_plex_location, "song.mp3")


        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=abs_plex_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(abs_plex_location)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, abs_plex_location) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {abs_plex_location}."
        )

    async def test_download_playlist_plex_command_location_relative(self):
        """Test download_playlist_plex_command with a relative path for location."""
        playlist_url = "test_plex_playlist_url_rel"
        rel_plex_location = "my_plex_playlist"
        expected_plex_path = os.path.join(plex_music_folder, rel_plex_location)
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_audio.reset_mock()
        self.cog.converter.convert_to_mp3.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.convert_to_mp3.return_value = os.path.join(expected_plex_path, "song.mp3")

        await self.cog.download_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=rel_plex_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_music_folder), call(expected_plex_path)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_audio_calls = [call(url, download_music_folder) for url in dummy_urls]
        self.cog.downloader.download_audio.assert_has_calls(download_audio_calls)

        convert_to_mp3_calls = [call(dummy_song_obj, expected_plex_path) for _ in dummy_urls]
        self.cog.converter.convert_to_mp3.assert_has_calls(convert_to_mp3_calls)

        clear_local_cache_calls = [call(download_music_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded song.mp3 to Plex at {expected_plex_path}."
        )

    # Tests for download_video_plex_command
    async def test_download_video_plex_command_location_none(self):
        """Test download_video_plex_command with location=None."""
        video_url = "test_video_plex_url_none"

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock()
        self.cog.converter.combine_video_and_audio.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.combine_video_and_audio.return_value = os.path.join(plex_video_folder, "video.mp4")

        await self.cog.download_video_plex_command.callback(self.cog, self.mock_interaction, video_url=video_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_video_folder), call(plex_video_folder)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_video.assert_called_once_with(video_url, download_video_folder)
        self.cog.converter.combine_video_and_audio.assert_called_once_with(dummy_video_obj, plex_video_folder)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_video_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video.mp4 to Plex server at {plex_video_folder}."
        )

    async def test_download_video_plex_command_location_absolute(self):
        """Test download_video_plex_command with an absolute path for location."""
        video_url = "test_video_plex_url_abs"
        abs_plex_video_location = "/custom/plex/videos/abs/path"

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock()
        self.cog.converter.combine_video_and_audio.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.combine_video_and_audio.return_value = os.path.join(abs_plex_video_location, "video.mp4")

        await self.cog.download_video_plex_command.callback(self.cog, self.mock_interaction, video_url=video_url, location=abs_plex_video_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_video_folder), call(abs_plex_video_location)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_video.assert_called_once_with(video_url, download_video_folder)
        self.cog.converter.combine_video_and_audio.assert_called_once_with(dummy_video_obj, abs_plex_video_location)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_video_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video.mp4 to Plex server at {abs_plex_video_location}."
        )

    async def test_download_video_plex_command_location_relative(self):
        """Test download_video_plex_command with a relative path for location."""
        video_url = "test_video_plex_url_rel"
        rel_plex_video_location = "my_plex_videos"
        expected_plex_video_path = os.path.join(plex_video_folder, rel_plex_video_location)

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock()
        self.cog.converter.combine_video_and_audio.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.converter.combine_video_and_audio.return_value = os.path.join(expected_plex_video_path, "video.mp4")

        await self.cog.download_video_plex_command.callback(self.cog, self.mock_interaction, video_url=video_url, location=rel_plex_video_location)

        self.mock_interaction.response.defer.assert_called_once()

        path_exists_calls = [call(download_video_folder), call(expected_plex_video_path)]
        self.cog.path_check.path_exists.assert_has_calls(path_exists_calls, any_order=True)

        self.cog.downloader.download_video.assert_called_once_with(video_url, download_video_folder)
        self.cog.converter.combine_video_and_audio.assert_called_once_with(dummy_video_obj, expected_plex_video_path)
        self.cog.path_check.clear_local_cache.assert_called_once_with(download_video_folder)

        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video.mp4 to Plex server at {expected_plex_video_path}."
        )

    # Tests for download_video_playlist_plex_command
    async def test_download_video_playlist_plex_command_location_none(self):
        """Test download_video_playlist_plex_command with location=None."""
        playlist_url = "test_video_plex_playlist_url_none"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock() # Changed from download_audio
        self.cog.converter.combine_video_and_audio.reset_mock() # Changed from convert_to_mp3
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        # Use the general video path for combined video
        self.cog.converter.combine_video_and_audio.return_value = os.path.join(plex_video_folder, "video.mp4")

        await self.cog.download_video_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_video_folder), call(plex_video_folder)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_video_calls = [call(url, download_video_folder) for url in dummy_urls]
        self.cog.downloader.download_video.assert_has_calls(download_video_calls)
        self.assertEqual(self.cog.downloader.download_video.call_count, len(dummy_urls))

        combine_video_calls = [call(dummy_video_obj, plex_video_folder) for _ in dummy_urls]
        self.cog.converter.combine_video_and_audio.assert_has_calls(combine_video_calls)
        self.assertEqual(self.cog.converter.combine_video_and_audio.call_count, len(dummy_urls))

        clear_local_cache_calls = [call(download_video_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)
        self.assertEqual(self.cog.path_check.clear_local_cache.call_count, len(dummy_urls))

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded video.mp4 to plex." # Message from the loop
        )
        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video playlist to Plex server at {plex_video_folder}." # Final message
        )


    async def test_download_video_playlist_plex_command_location_absolute(self):
        """Test download_video_playlist_plex_command with an absolute path for location."""
        playlist_url = "test_video_plex_playlist_url_abs"
        abs_plex_video_location = "/custom/plex/videos/abs/playlist/path"
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock()
        self.cog.converter.combine_video_and_audio.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.combine_video_and_audio.return_value = os.path.join(abs_plex_video_location, "video.mp4")

        await self.cog.download_video_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=abs_plex_video_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_video_folder), call(abs_plex_video_location)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_video_calls = [call(url, download_video_folder) for url in dummy_urls]
        self.cog.downloader.download_video.assert_has_calls(download_video_calls)

        combine_video_calls = [call(dummy_video_obj, abs_plex_video_location) for _ in dummy_urls]
        self.cog.converter.combine_video_and_audio.assert_has_calls(combine_video_calls)

        clear_local_cache_calls = [call(download_video_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded video.mp4 to plex."
        )
        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video playlist to Plex server at {abs_plex_video_location}."
        )

    async def test_download_video_playlist_plex_command_location_relative(self):
        """Test download_video_playlist_plex_command with a relative path for location."""
        playlist_url = "test_video_plex_playlist_url_rel"
        rel_plex_video_location = "my_plex_video_playlist"
        expected_plex_video_path = os.path.join(plex_video_folder, rel_plex_video_location)
        dummy_urls = ["url1", "url2"]

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_video.reset_mock()
        self.cog.converter.combine_video_and_audio.reset_mock()
        self.cog.path_check.clear_local_cache.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()
        self.cog.downloader.get_playlist.reset_mock()

        self.cog.downloader.get_playlist.return_value = dummy_urls
        self.cog.converter.combine_video_and_audio.return_value = os.path.join(expected_plex_video_path, "video.mp4")

        await self.cog.download_video_playlist_plex_command.callback(self.cog, self.mock_interaction, playlist_url=playlist_url, location=rel_plex_video_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.downloader.get_playlist.assert_called_once_with(playlist_url)

        initial_path_exists_calls = [call(download_video_folder), call(expected_plex_video_path)]
        self.cog.path_check.path_exists.assert_has_calls(initial_path_exists_calls, any_order=True)

        download_video_calls = [call(url, download_video_folder) for url in dummy_urls]
        self.cog.downloader.download_video.assert_has_calls(download_video_calls)

        combine_video_calls = [call(dummy_video_obj, expected_plex_video_path) for _ in dummy_urls]
        self.cog.converter.combine_video_and_audio.assert_has_calls(combine_video_calls)

        clear_local_cache_calls = [call(download_video_folder) for _ in dummy_urls]
        self.cog.path_check.clear_local_cache.assert_has_calls(clear_local_cache_calls)

        self.mock_interaction.followup.send.assert_any_call(
            f"Downloaded video.mp4 to plex."
        )
        self.mock_interaction.followup.send.assert_any_call(
            f"Finished downloading video playlist to Plex server at {expected_plex_video_path}."
        )

    # Tests for download_spotify_command
    @patch('os.path.exists')
    async def test_download_spotify_command_location_none(self, mock_os_path_exists):
        """Test download_spotify_command with location=None."""
        spotify_url = "test_spotify_url_none"
        mock_os_path_exists.return_value = True # Assume file exists after download

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_spotify.reset_mock()
        self.cog.path_check.get_temp_spotify_file.reset_mock()
        self.cog.path_check.clear_temp_spotify.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        # Configure get_temp_spotify_file to return a path consistent with temp_spotify_folder
        self.cog.path_check.get_temp_spotify_file.return_value = os.path.join(temp_spotify_folder, "song.mp3")

        await self.cog.download_spotify_command.callback(self.cog, self.mock_interaction, url=spotify_url, location=None)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.path_check.path_exists.assert_called_once_with(temp_spotify_folder)
        self.cog.downloader.download_spotify.assert_called_once_with(spotify_url, temp_spotify_folder)
        self.cog.path_check.get_temp_spotify_file.assert_called_once_with(temp_spotify_folder)

        # Check that os.path.exists was called with the path returned by get_temp_spotify_file
        mock_os_path_exists.assert_called_once_with(os.path.join(temp_spotify_folder, "song.mp3"))

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")
        self.cog.path_check.clear_temp_spotify.assert_called_once_with(temp_spotify_folder)

    @patch('os.path.exists')
    async def test_download_spotify_command_location_absolute(self, mock_os_path_exists):
        """Test download_spotify_command with an absolute path for location."""
        spotify_url = "test_spotify_url_abs"
        abs_spotify_location = "/custom/spotify/abs/path"
        mock_os_path_exists.return_value = True

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_spotify.reset_mock()
        self.cog.path_check.get_temp_spotify_file.reset_mock()
        self.cog.path_check.clear_temp_spotify.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.path_check.get_temp_spotify_file.return_value = os.path.join(abs_spotify_location, "song.mp3")

        await self.cog.download_spotify_command.callback(self.cog, self.mock_interaction, url=spotify_url, location=abs_spotify_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.path_check.path_exists.assert_called_once_with(abs_spotify_location)
        self.cog.downloader.download_spotify.assert_called_once_with(spotify_url, abs_spotify_location)
        self.cog.path_check.get_temp_spotify_file.assert_called_once_with(abs_spotify_location)

        mock_os_path_exists.assert_called_once_with(os.path.join(abs_spotify_location, "song.mp3"))

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")
        self.cog.path_check.clear_temp_spotify.assert_called_once_with(abs_spotify_location)

    @patch('os.path.exists')
    async def test_download_spotify_command_location_relative(self, mock_os_path_exists):
        """Test download_spotify_command with a relative path for location."""
        spotify_url = "test_spotify_url_rel"
        rel_spotify_location = "my_spotify_downloads"
        expected_spotify_path = os.path.join(temp_spotify_folder, rel_spotify_location)
        mock_os_path_exists.return_value = True

        # Reset mocks
        self.cog.path_check.path_exists.reset_mock()
        self.cog.downloader.download_spotify.reset_mock()
        self.cog.path_check.get_temp_spotify_file.reset_mock()
        self.cog.path_check.clear_temp_spotify.reset_mock()
        self.mock_interaction.followup.send.reset_mock()
        self.mock_interaction.response.defer.reset_mock()

        self.cog.path_check.get_temp_spotify_file.return_value = os.path.join(expected_spotify_path, "song.mp3")

        await self.cog.download_spotify_command.callback(self.cog, self.mock_interaction, url=spotify_url, location=rel_spotify_location)

        self.mock_interaction.response.defer.assert_called_once()
        self.cog.path_check.path_exists.assert_called_once_with(expected_spotify_path)
        self.cog.downloader.download_spotify.assert_called_once_with(spotify_url, expected_spotify_path)
        self.cog.path_check.get_temp_spotify_file.assert_called_once_with(expected_spotify_path)

        mock_os_path_exists.assert_called_once_with(os.path.join(expected_spotify_path, "song.mp3"))

        self.mock_interaction.followup.send.assert_any_call(file=unittest.mock.ANY, content="song.mp3")
        self.cog.path_check.clear_temp_spotify.assert_called_once_with(expected_spotify_path)


if __name__ == '__main__':
    unittest.main()
