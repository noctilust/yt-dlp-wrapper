"""
Unit tests for yt-dlp-wrapper.

The script file has a hyphen (`yt-dlp-wrapper.py`) so we load it via importlib
under the name `wrapper`. Tests bypass the real `__init__` (which shells out to
check yt-dlp/ffmpeg/browser) by using `VideoDownloader.__new__`.
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WRAPPER_PATH = Path(__file__).parent / "yt-dlp-wrapper.py"

spec = importlib.util.spec_from_file_location("wrapper", WRAPPER_PATH)
wrapper = importlib.util.module_from_spec(spec)
sys.modules["wrapper"] = wrapper
spec.loader.exec_module(wrapper)

VideoDownloader = wrapper.VideoDownloader
YtDlpWrapperError = wrapper.YtDlpWrapperError
YOUTUBE_CLIENTS = wrapper.YOUTUBE_CLIENTS


def make_downloader():
    """Create a VideoDownloader instance without running __init__."""
    dl = VideoDownloader.__new__(VideoDownloader)
    dl.cookies_browser = "chrome"
    dl.cookies_browser_arg = "chrome"
    return dl


class TestFindPremiumFormat(unittest.TestCase):
    def test_no_premium_returns_none(self):
        dl = make_downloader()
        result = dl.find_premium_format(
            {"formats": [{"format_id": "18", "format_note": "medium", "height": 360}]}
        )
        self.assertIsNone(result)

    def test_single_premium_picked(self):
        dl = make_downloader()
        result = dl.find_premium_format(
            {
                "formats": [
                    {"format_id": "18", "format_note": "medium", "height": 360},
                    {"format_id": "356", "format_note": "1080p Premium", "height": 1080},
                ]
            }
        )
        self.assertEqual(result, "356+bestaudio/best")

    def test_multiple_premium_picks_highest(self):
        dl = make_downloader()
        result = dl.find_premium_format(
            {
                "formats": [
                    {"format_id": "356", "format_note": "1080p Premium", "height": 1080},
                    {"format_id": "401", "format_note": "1440p Premium", "height": 1440},
                    {"format_id": "620", "format_note": "2160p Premium", "height": 2160},
                ]
            }
        )
        self.assertEqual(result, "620+bestaudio/best")

    def test_missing_height_is_skipped(self):
        dl = make_downloader()
        result = dl.find_premium_format(
            {
                "formats": [
                    {"format_id": "999", "format_note": "Premium", "height": None},
                ]
            }
        )
        self.assertIsNone(result)

    def test_empty_formats(self):
        dl = make_downloader()
        self.assertIsNone(dl.find_premium_format({}))
        self.assertIsNone(dl.find_premium_format({"formats": None}))

    def test_malformed_entries_skipped(self):
        dl = make_downloader()
        result = dl.find_premium_format(
            {
                "formats": [
                    "not-a-dict",
                    {"format_note": "Premium"},  # no format_id
                    {"format_id": "356", "format_note": "1080p Premium", "height": 720},
                ]
            }
        )
        self.assertEqual(result, "356+bestaudio/best")

    def test_real_uptown_funk_shape(self):
        """Exact JSON shape from a live Premium video (Uptown Funk)."""
        dl = make_downloader()
        result = dl.find_premium_format(
            {
                "formats": [
                    {"format_id": "356", "height": 1080, "vcodec": "vp9",
                     "format_note": "1080p Premium",
                     "format": "356 - 1920x1080 (1080p Premium)"},
                    {"format_id": "721", "height": 1080, "vcodec": "av01.0.08M.08",
                     "format_note": "1080p Premium",
                     "format": "721 - 1920x1080 (1080p Premium)"},
                ]
            }
        )
        self.assertEqual(result, "356+bestaudio/best")


class TestCreateOutputDir(unittest.TestCase):
    def setUp(self):
        self._orig_home = Path.home()
        self.tmp_home = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_home, ignore_errors=True)

    def _dl(self):
        dl = make_downloader()
        return dl

    def test_strips_path_chars(self):
        dl = self._dl()
        with mock.patch.object(Path, "home", return_value=Path(self.tmp_home)):
            out = dl.create_output_dir('A"b/c\\d:e*f?g<h>i|j', "20240101")
        # Path chars replaced with empty string (then strip)
        self.assertIn("Abcdefghij", out.name)
        self.assertNotIn('"', out.name)
        self.assertNotIn(":", out.name)

    def test_strips_trailing_dots_and_spaces(self):
        dl = self._dl()
        with mock.patch.object(Path, "home", return_value=Path(self.tmp_home)):
            out = dl.create_output_dir("My Video...   ", "20240101")
        # The sanitized title should not end with dots or spaces before the
        # " - " delimiter
        sanitized = out.name.split(" - ", 1)[1]
        self.assertFalse(sanitized.endswith("."))
        self.assertFalse(sanitized.endswith(" "))

    def test_invalid_date_falls_back_to_today(self):
        dl = self._dl()
        with mock.patch.object(Path, "home", return_value=Path(self.tmp_home)):
            out = dl.create_output_dir("Test", "not-a-date")
        # Should be a YYYY.MM.DD formatted today
        from datetime import datetime
        today = datetime.now().strftime("%Y.%m.%d")
        self.assertTrue(out.name.startswith(today))

    def test_missing_date_falls_back_to_today(self):
        dl = self._dl()
        with mock.patch.object(Path, "home", return_value=Path(self.tmp_home)):
            out = dl.create_output_dir("Test", None)
        from datetime import datetime
        today = datetime.now().strftime("%Y.%m.%d")
        self.assertTrue(out.name.startswith(today))

    def test_long_title_truncated(self):
        dl = self._dl()
        long_title = "A" * 200
        with mock.patch.object(Path, "home", return_value=Path(self.tmp_home)):
            out = dl.create_output_dir(long_title, "20240101")
        sanitized = out.name.split(" - ", 1)[1]
        self.assertLessEqual(len(sanitized), 100)


class TestDetectPlatform(unittest.TestCase):
    def test_youtube_com(self):
        self.assertEqual(
            make_downloader().detect_platform("https://www.youtube.com/watch?v=abc"),
            "youtube",
        )

    def test_youtu_be(self):
        self.assertEqual(
            make_downloader().detect_platform("https://youtu.be/abc"),
            "youtube",
        )

    def test_twitter(self):
        self.assertEqual(
            make_downloader().detect_platform("https://twitter.com/user/status/123"),
            "x",
        )

    def test_x_com(self):
        self.assertEqual(
            make_downloader().detect_platform("https://x.com/user/status/123"),
            "x",
        )

    def test_other(self):
        self.assertEqual(
            make_downloader().detect_platform("https://example.com/video/123"),
            "other",
        )

    def test_subdomain_of_youtube_matches(self):
        self.assertEqual(
            make_downloader().detect_platform("https://www.youtube.com/watch?v=abc"),
            "youtube",
        )

    def test_youtube_in_path_only_returns_other(self):
        # 'youtube.com' in the path or query must not match
        self.assertEqual(
            make_downloader().detect_platform("https://example.com/?ref=youtube.com"),
            "other",
        )

    def test_lookalike_subdomain_returns_other(self):
        # 'twitter.com.evil.com' must not match 'twitter.com'
        self.assertEqual(
            make_downloader().detect_platform("https://twitter.com.evil.com/user"),
            "other",
        )

    def test_youtu_be_https_no_subdomain(self):
        self.assertEqual(
            make_downloader().detect_platform("https://youtu.be/abc"),
            "youtube",
        )


class TestDownloadVideoFailFast(unittest.TestCase):
    """Bug #3: empty info must not produce a colliding 'video' folder."""

    def test_empty_info_raises(self):
        dl = make_downloader()
        dl.get_video_info = lambda u: {}
        dl._validate_youtube_requirements = lambda u: None
        dl._validate_pot_provider = lambda u, m: None

        with self.assertRaises(YtDlpWrapperError) as ctx:
            dl.download_video("https://www.youtube.com/watch?v=abc")
        self.assertIn("metadata", str(ctx.exception).lower())


class TestRunDownloadStderrCapture(unittest.TestCase):
    """Bug #1: stderr must be captured so SABR/PO Token detection fires."""

    def test_sabr_stderr_triggers_fallback(self):
        url = "https://www.youtube.com/watch?v=test"
        dl = make_downloader()
        # Bypass the slow parts
        dl._check_pot_plugin_installed = lambda: True

        # Mock subprocess.run:
        #   - first call: simulate a download failure with SABR stderr
        #   - subsequent calls: simulate success
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                # First call: fail with SABR stderr
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="ERROR: YouTube is forcing SABR streaming for this client",
                    output="",
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with mock.patch.object(wrapper.subprocess, "run", side_effect=fake_run):
                ok = dl._run_download(
                    url=url,
                    extra_args=[],
                    format_selector="best",
                    youtube_client="web",  # user specified a client
                    try_sabr=False,
                    try_fallback_clients=True,
                    sponsorblock_mark=None,
                    sponsorblock_remove=None,
                    embed_chapters=False,
                    sleep_interval=None,
                    sleep_subtitles=None,
                    pot_provider_mode=None,
                    pot_provider_url=None,
                    pot_provider_script=None,
                    platform="youtube",
                    output_dir=out,
                )
            self.assertTrue(ok)
            # First call: stderr=PIPE captured
            self.assertEqual(calls[0].get("stderr"), subprocess.PIPE)
            # stdout inherited (None) so progress shows in terminal
            self.assertIsNone(calls[0].get("stdout"))
            # Multiple subprocess calls (original + at least one fallback)
            self.assertGreater(len(calls), 1)


class TestRunDownloadNoMetadataRefetch(unittest.TestCase):
    """Bug #2: recursive fallback must not re-fetch metadata."""

    def test_metadata_fetched_only_once(self):
        url = "https://www.youtube.com/watch?v=test"
        dl = make_downloader()
        dl._check_pot_plugin_installed = lambda: True

        # Stub get_video_info directly (avoid patching subprocess twice)
        info_calls = []

        def fake_get_info(u):
            info_calls.append(u)
            return {
                "title": "Test",
                "upload_date": "20240101",
                "formats": [],
            }

        dl.get_video_info = fake_get_info
        dl._validate_youtube_requirements = lambda u: None
        dl._validate_pot_provider = lambda u, m: None

        # First download subprocess call fails with SABR; rest succeed
        download_calls = [0]

        def fake_run(cmd, **kwargs):
            download_calls[0] += 1
            if download_calls[0] == 1:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="YouTube is forcing SABR streaming for this client",
                    output="",
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dl.create_output_dir = lambda t, d: out

            with mock.patch.object(wrapper.subprocess, "run", side_effect=fake_run):
                ok = dl.download_video(url, try_fallback_clients=True)

            self.assertTrue(ok)
            # Metadata was fetched exactly once even though we had multiple
            # fallback attempts.
            self.assertEqual(len(info_calls), 1)
            # We made at least 2 download subprocess calls (1 fail + 1+ success)
            self.assertGreaterEqual(download_calls[0], 2)


class TestRunDownloadNoFallbackWhenDisabled(unittest.TestCase):
    def test_no_fallback_does_not_recurse(self):
        url = "https://www.youtube.com/watch?v=test"
        dl = make_downloader()
        dl._check_pot_plugin_installed = lambda: True

        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                stderr="YouTube is forcing SABR streaming",
                output="",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with mock.patch.object(wrapper.subprocess, "run", side_effect=fake_run):
                ok = dl._run_download(
                    url=url,
                    extra_args=[],
                    format_selector="best",
                    youtube_client="web",
                    try_sabr=False,
                    try_fallback_clients=False,  # disabled
                    sponsorblock_mark=None,
                    sponsorblock_remove=None,
                    embed_chapters=False,
                    sleep_interval=None,
                    sleep_subtitles=None,
                    pot_provider_mode=None,
                    pot_provider_url=None,
                    pot_provider_script=None,
                    platform="youtube",
                    output_dir=out,
                )
            self.assertFalse(ok)
            # Only one attempt when fallback is disabled
            self.assertEqual(call_count[0], 1)


class TestCheckPotPluginInstalled(unittest.TestCase):
    def test_installed_plugin_returns_true(self):
        dl = make_downloader()
        with mock.patch("importlib.util.find_spec", return_value=object()):
            self.assertTrue(dl._check_pot_plugin_installed())

    def test_missing_plugin_returns_false(self):
        dl = make_downloader()
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(dl._check_pot_plugin_installed())


class TestBuildCommand(unittest.TestCase):
    def test_basic_youtube_command(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(
                url="https://www.youtube.com/watch?v=abc",
                extra_args=[],
                format_selector="best",
                youtube_client=None,
                try_sabr=False,
                sponsorblock_mark=None,
                sponsorblock_remove=None,
                embed_chapters=False,
                sleep_interval=None,
                sleep_subtitles=None,
                pot_provider_mode=None,
                pot_provider_url=None,
                pot_provider_script=None,
                platform="youtube",
                output_dir=out,
            )
        self.assertEqual(cmd[0], "yt-dlp")
        self.assertIn("--cookies-from-browser", cmd)
        self.assertIn("chrome", cmd)
        self.assertIn("-f", cmd)
        self.assertIn("best", cmd)
        self.assertIn("--write-auto-sub", cmd)
        self.assertIn("--embed-metadata", cmd)
        # No embed-chapters when not requested
        self.assertNotIn("--embed-chapters", cmd)
        # No sponsorblock when not requested
        self.assertNotIn("--sponsorblock-mark", cmd)
        # URL is last
        self.assertEqual(cmd[-1], "https://www.youtube.com/watch?v=abc")

    def test_sponsorblock_youtube_only(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            yt_cmd = dl._build_command(
                url="https://www.youtube.com/watch?v=abc",
                extra_args=[],
                format_selector="best",
                youtube_client=None,
                try_sabr=False,
                sponsorblock_mark="all",
                sponsorblock_remove=None,
                embed_chapters=False,
                sleep_interval=None,
                sleep_subtitles=None,
                pot_provider_mode=None,
                pot_provider_url=None,
                pot_provider_script=None,
                platform="youtube",
                output_dir=out,
            )
            tw_cmd = dl._build_command(
                url="https://twitter.com/user/status/123",
                extra_args=[],
                format_selector="best",
                youtube_client=None,
                try_sabr=False,
                sponsorblock_mark="all",
                sponsorblock_remove=None,
                embed_chapters=False,
                sleep_interval=None,
                sleep_subtitles=None,
                pot_provider_mode=None,
                pot_provider_url=None,
                pot_provider_script=None,
                platform="x",
                output_dir=out,
            )
        self.assertIn("--sponsorblock-mark", yt_cmd)
        self.assertIn("all", yt_cmd)
        # Twitter: sponsorblock must not appear
        self.assertNotIn("--sponsorblock-mark", tw_cmd)

    def test_youtube_client_combined_with_sabr(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(
                url="https://www.youtube.com/watch?v=abc",
                extra_args=[],
                format_selector="best",
                youtube_client="tv",
                try_sabr=True,
                sponsorblock_mark=None,
                sponsorblock_remove=None,
                embed_chapters=False,
                sleep_interval=None,
                sleep_subtitles=None,
                pot_provider_mode=None,
                pot_provider_url=None,
                pot_provider_script=None,
                platform="youtube",
                output_dir=out,
            )
        # Find the --extractor-args value
        i = cmd.index("--extractor-args")
        arg = cmd[i + 1]
        # Both player-client AND formats=duplicate should be present, semicolon-joined
        self.assertIn("youtube:player-client=tv", arg)
        self.assertIn("youtube:formats=duplicate", arg)
        self.assertIn(";", arg)

    def test_pot_provider_args_appended(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(
                url="https://www.youtube.com/watch?v=abc",
                extra_args=[],
                format_selector="best",
                youtube_client="tv",
                try_sabr=False,
                sponsorblock_mark=None,
                sponsorblock_remove=None,
                embed_chapters=False,
                sleep_interval=None,
                sleep_subtitles=None,
                pot_provider_mode=None,
                pot_provider_url="http://example.com:9999",
                pot_provider_script=None,
                platform="youtube",
                output_dir=out,
            )
        i = cmd.index("--extractor-args")
        arg = cmd[i + 1]
        self.assertIn("youtubepot-bgutilhttp:base_url=http://example.com:9999", arg)


if __name__ == "__main__":
    unittest.main()
