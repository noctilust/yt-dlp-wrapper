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
DownloadOptions = wrapper.DownloadOptions


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


class TestGetVideoInfoRaises(unittest.TestCase):
    """B: get_video_info now raises YtDlpWrapperError instead of returning {}."""

    def test_subprocess_failure_raises(self):
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=1, stdout="", stderr="auth failed"
            ),
        ):
            with self.assertRaises(YtDlpWrapperError) as ctx:
                dl.get_video_info("https://www.youtube.com/watch?v=abc")
        self.assertIn("auth failed", str(ctx.exception))

    def test_timeout_raises(self):
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd="yt-dlp", timeout=300),
        ):
            with self.assertRaises(YtDlpWrapperError) as ctx:
                dl.get_video_info("https://www.youtube.com/watch?v=abc")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_invalid_json_raises(self):
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=0, stdout="not json", stderr=""
            ),
        ):
            with self.assertRaises(YtDlpWrapperError):
                dl.get_video_info("https://www.youtube.com/watch?v=abc")

    def test_valid_json_returns_dict(self):
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=0,
                stdout='{"title": "x", "formats": []}', stderr=""
            ),
        ):
            info = dl.get_video_info("https://www.youtube.com/watch?v=abc")
        self.assertEqual(info["title"], "x")

    def test_get_video_info_adds_ejs_remote_for_youtube(self):
        """Ensure metadata fetch for YouTube includes EJS remote fallback."""
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=0,
                stdout='{"title": "x", "formats": []}', stderr=""
            ),
        ) as mock_run:
            dl.get_video_info("https://www.youtube.com/watch?v=abc")
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("--remote-components", called_cmd)
        self.assertIn("ejs:github", called_cmd)
        self.assertIn("-j", called_cmd)

    def test_get_video_info_no_ejs_remote_for_non_youtube(self):
        """Non-YouTube metadata fetch must not include EJS remote components."""
        dl = make_downloader()
        with mock.patch.object(
            wrapper.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=["yt-dlp"], returncode=0,
                stdout='{"title": "x"}', stderr=""
            ),
        ) as mock_run:
            dl.get_video_info("https://twitter.com/user/status/123")
        called_cmd = mock_run.call_args[0][0]
        self.assertNotIn("--remote-components", called_cmd)


class TestDownloadVideoPropagates(unittest.TestCase):
    """B: download_video should not catch get_video_info errors."""

    def test_get_video_info_failure_propagates(self):
        dl = make_downloader()
        # Simulate get_video_info raising (e.g., bad cookies)
        dl.get_video_info = mock.Mock(
            side_effect=YtDlpWrapperError("cookies invalid")
        )
        dl._validate_youtube_requirements = lambda u: None
        dl._validate_pot_provider = lambda u, m: None
        dl._check_pot_plugin_installed = lambda: True

        with self.assertRaises(YtDlpWrapperError) as ctx:
            dl.download_video(DownloadOptions(url="https://www.youtube.com/watch?v=abc"))
        self.assertIn("cookies invalid", str(ctx.exception))


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
                ok = dl._run_download(DownloadOptions(
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
                ))
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

        def fake_get_info(u, opts=None):
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
                ok = dl.download_video(DownloadOptions(
                    url=url,
                    try_fallback_clients=True,
                ))

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
                ok = dl._run_download(DownloadOptions(
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
                ))
            self.assertFalse(ok)
            # Only one attempt when fallback is disabled
            self.assertEqual(call_count[0], 1)


class TestResolveBrowser(unittest.TestCase):
    """C: _resolve_browser fallback chain is untested."""

    def test_preferred_available_returns_preferred(self):
        dl = make_downloader()
        dl._is_browser_available = lambda b: b == "chrome"
        result = dl._resolve_browser("chrome")
        self.assertEqual(result, "chrome")
        self.assertEqual(dl.cookies_browser_arg, "chrome")

    def test_preferred_missing_falls_back(self):
        dl = make_downloader()
        # Only firefox is available
        dl._is_browser_available = lambda b: b == "firefox"
        result = dl._resolve_browser("chrome")
        # Falls back to firefox (next in BROWSER_FALLBACK_ORDER)
        self.assertEqual(result, "firefox")
        self.assertEqual(dl.cookies_browser_arg, "firefox")

    def test_no_browsers_returns_preferred(self):
        dl = make_downloader()
        dl._is_browser_available = lambda b: False
        result = dl._resolve_browser("chrome")
        # No browsers found — keeps preferred and warns
        self.assertEqual(result, "chrome")
        self.assertEqual(dl.cookies_browser_arg, "chrome")

    def test_safari_fallback(self):
        dl = make_downloader()
        # chrome and firefox missing, safari available
        dl._is_browser_available = lambda b: b == "safari"
        result = dl._resolve_browser("chrome")
        self.assertEqual(result, "safari")
        self.assertEqual(dl.cookies_browser_arg, "safari")


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
            cmd = dl._build_command(DownloadOptions(
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
            ))
        self.assertEqual(cmd[0], "yt-dlp")
        self.assertIn("--cookies-from-browser", cmd)
        self.assertIn("chrome", cmd)
        self.assertIn("-f", cmd)
        self.assertIn("best", cmd)
        self.assertIn("--write-auto-sub", cmd)
        self.assertIn("--embed-metadata", cmd)
        # EJS remote component fallback must be present for YouTube
        self.assertIn("--remote-components", cmd)
        self.assertIn("ejs:github", cmd)
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
            yt_cmd = dl._build_command(DownloadOptions(
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
            ))
            tw_cmd = dl._build_command(DownloadOptions(
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
            ))
        self.assertIn("--sponsorblock-mark", yt_cmd)
        self.assertIn("all", yt_cmd)
        # YouTube: EJS remote must appear (YouTube-only)
        self.assertIn("--remote-components", yt_cmd)
        self.assertIn("ejs:github", yt_cmd)
        # Twitter: sponsorblock and EJS remote must not appear
        self.assertNotIn("--sponsorblock-mark", tw_cmd)
        self.assertNotIn("--remote-components", tw_cmd)

    def test_youtube_client_combined_with_sabr(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(DownloadOptions(
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
            ))
        # Find the --extractor-args value
        i = cmd.index("--extractor-args")
        arg = cmd[i + 1]
        self.assertEqual(arg, "youtube:player-client=tv;formats=duplicate")

    def test_pot_provider_args_appended(self):
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(DownloadOptions(
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
            ))
        extractor_args = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--extractor-args']
        self.assertEqual(extractor_args, [
            "youtube:player-client=tv",
            "youtubepot-bgutilhttp:base_url=http://example.com:9999",
        ])

    def test_ejs_remote_allows_override_via_extra_args(self):
        """Pass-through --no-remote-components (or ejs:npm) is appended after internal for YT."""
        dl = make_downloader()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = dl._build_command(DownloadOptions(
                url="https://www.youtube.com/watch?v=abc",
                extra_args=["--no-remote-components"],
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
            ))
        # User overrides are appended after wrapper defaults.
        self.assertIn("--remote-components", cmd)
        self.assertIn("ejs:github", cmd)
        self.assertIn("--no-remote-components", cmd)
        # no- appears after the positive (later flags win for disallow)
        self.assertGreater(cmd.index("--no-remote-components"), cmd.index("--remote-components"))


class TestUpstreamCompatibility(unittest.TestCase):
    def test_version_warning_uses_recommended_release(self):
        dl = make_downloader()
        for version, should_warn in [('2026.03.17', True), ('2026.08.19', False),
                                     ('2026.08.20.123456', False), ('custom-build', False)]:
            with self.subTest(version=version), mock.patch.object(wrapper.shutil, 'which', return_value='/bin/tool'), \
                 mock.patch.object(dl, '_resolve_browser', return_value='chrome'), \
                 mock.patch.object(wrapper.subprocess, 'run', return_value=subprocess.CompletedProcess(
                     args=[], returncode=0, stdout=version, stderr=''
                 )), mock.patch.object(wrapper.logger, 'warning') as warning:
                dl._validate_dependencies()
                if should_warn:
                    self.assertIn('2026.08.19+', warning.call_args.args[0])
                else:
                    warning.assert_not_called()

    def test_current_clients_and_manual_only_android_vr(self):
        self.assertIn('visionos', YOUTUBE_CLIENTS)
        self.assertIn('ios', YOUTUBE_CLIENTS)
        self.assertIn('tv_simply', YOUTUBE_CLIENTS)
        self.assertNotIn('android_music', YOUTUBE_CLIENTS)
        self.assertIn('android_vr', YOUTUBE_CLIENTS)
        self.assertNotIn('android_vr', wrapper.YOUTUBE_FALLBACK_CLIENTS)

    def test_quickjs_executable_and_runtime_priority(self):
        dl = make_downloader()
        for executables, expected in [({'qjs', 'bun'}, 'quickjs'), ({'node', 'qjs'}, 'node'),
                                      ({'deno', 'node'}, 'deno'), (set(), None)]:
            with self.subTest(executables=executables), mock.patch.object(
                wrapper.shutil, 'which', side_effect=lambda exe: exe if exe in executables else None
            ):
                self.assertEqual(dl._check_javascript_runtime(), expected)

    def test_alternative_runtime_enabled_in_metadata_and_download(self):
        dl = make_downloader()
        opts = DownloadOptions(url='https://youtu.be/test', format_selector='best',
                               platform='youtube', output_dir=Path('/tmp/test'))
        for runtime in ('node', 'quickjs', 'bun'):
            with self.subTest(runtime=runtime), mock.patch.object(
                dl, '_check_javascript_runtime', return_value=runtime
            ), mock.patch.object(wrapper.subprocess, 'run', return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout='{"title":"Test"}', stderr=''
            )) as run:
                dl.get_video_info(opts.url, opts)
                for cmd in (run.call_args.args[0], dl._build_command(opts)):
                    self.assertEqual(cmd[cmd.index('--js-runtimes') + 1], runtime)

    def test_user_runtime_controls_disable_auto_selection(self):
        dl = make_downloader()
        for extra in (['--no-js-runtimes'], ['--js-runtimes', 'node:/custom/node'],
                      ['--no-js-runtimes', '--js-runtimes=quickjs:/custom/qjs']):
            with self.subTest(extra=extra), mock.patch.object(dl, '_check_javascript_runtime') as runtime:
                args = dl._build_extraction_args(DownloadOptions(url='https://youtu.be/test', extra_args=extra))
                runtime.assert_not_called()
                self.assertNotIn('--js-runtimes', args)

    def test_metadata_receives_client_provider_and_extraction_overrides(self):
        dl = make_downloader()
        opts = DownloadOptions(
            url='https://youtu.be/test', youtube_client='tv_downgraded', try_sabr=True,
            pot_provider_url='http://localhost:8080', pot_provider_script='/tmp/provider.js',
            extra_args=['--no-remote-components', '--no-js-runtimes',
                        '--js-runtimes=node:/custom/node', '--extractor-args', 'youtube:lang=en',
                        '--no-playlist', '--limit-rate', '1M', '--exec', 'echo downloaded'],
        )
        with mock.patch.object(wrapper.subprocess, 'run', return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"title":"Test"}', stderr=''
        )) as run:
            dl.get_video_info(opts.url, opts)
        cmd = run.call_args.args[0]
        self.assertIn('youtube:player-client=tv_downgraded;formats=duplicate', cmd)
        self.assertIn('youtubepot-bgutilhttp:base_url=http://localhost:8080', cmd)
        self.assertIn('youtubepot-bgutilscript:script_path=/tmp/provider.js', cmd)
        self.assertGreater(cmd.index('--no-remote-components'), cmd.index('--remote-components'))
        self.assertIn('--js-runtimes=node:/custom/node', cmd)
        self.assertIn('youtube:lang=en', cmd)
        self.assertIn('--no-playlist', cmd)
        self.assertIn('--simulate', cmd)
        self.assertIn('--ignore-no-formats-error', cmd)
        self.assertNotIn('--exec', cmd)
        self.assertNotIn('--limit-rate', cmd)

    def test_download_passes_options_into_metadata(self):
        dl = make_downloader()
        opts = DownloadOptions(url='https://youtu.be/test', youtube_client='visionos')
        with mock.patch.object(dl, '_validate_youtube_requirements'), \
             mock.patch.object(dl, '_validate_pot_provider'), \
             mock.patch.object(dl, 'get_video_info', return_value={'title': 'Test'}) as info, \
             mock.patch.object(dl, 'create_output_dir', return_value=Path('/tmp/test')), \
             mock.patch.object(dl, '_run_download', return_value=True):
            self.assertTrue(dl.download_video(opts))
        info.assert_called_once_with(opts.url, opts)

    def test_fallback_preserves_provider_args_and_replaces_user_client(self):
        extra = ['--extractor-args', 'youtube:player_client=web;lang=en',
                 '--extractor-args=youtube:formats=duplicate;player-client=web',
                 '--extractor-args', 'youtubepot-bgutilhttp:base_url=http://localhost:8080',
                 '--no-remote-components']
        expected = ['--extractor-args', 'youtube:lang=en;player-client=tv_downgraded',
                    '--extractor-args=youtube:formats=duplicate;player-client=tv_downgraded',
                    '--extractor-args', 'youtubepot-bgutilhttp:base_url=http://localhost:8080',
                    '--no-remote-components']
        self.assertEqual(VideoDownloader._fallback_extra_args(extra, 'tv_downgraded'), expected)
        self.assertEqual(extra[1], 'youtube:player_client=web;lang=en')

    def test_duplicate_formats_flag_and_legacy_alias(self):
        for flag in ('--include-duplicate-formats', '--enable-sabr'):
            with self.subTest(flag=flag), mock.patch.object(sys, 'argv', ['wrapper', 'https://youtu.be/test', flag]), \
                 mock.patch.object(wrapper, 'VideoDownloader') as downloader:
                downloader.return_value.download_video.return_value = True
                with self.assertRaises(SystemExit) as ctx:
                    wrapper.main()
                self.assertEqual(ctx.exception.code, 0)
                self.assertTrue(downloader.return_value.download_video.call_args.args[0].try_sabr)

    def test_po_token_error_retries_explicit_client_and_preserves_provider(self):
        dl = make_downloader()
        opts = DownloadOptions(
            url='https://youtu.be/test', youtube_client='web', try_fallback_clients=True,
            format_selector='best', platform='youtube', output_dir=Path('/tmp/test'),
            extra_args=['--extractor-args', 'youtube:lang=en;player-client=web',
                        '--extractor-args', 'youtubepot-bgutilhttp:base_url=http://localhost:8080'],
        )
        with mock.patch.object(dl, '_check_pot_plugin_installed', return_value=True), \
             mock.patch.object(wrapper.subprocess, 'run', side_effect=[
                 subprocess.CalledProcessError(1, [], stderr='ERROR: requires a GVS PO Token'),
                 subprocess.CompletedProcess([], 0),
             ]) as run:
            self.assertTrue(dl._run_download(opts))
        retry_cmd = run.call_args_list[1].args[0]
        self.assertIn('youtube:lang=en;player-client=web_embedded', retry_cmd)
        self.assertIn('youtubepot-bgutilhttp:base_url=http://localhost:8080', retry_cmd)

    def test_exhausted_fallbacks_do_not_attempt_fake_sabr_support(self):
        dl = make_downloader()
        opts = DownloadOptions(
            url='https://youtu.be/test', try_fallback_clients=True,
            format_selector='best', platform='youtube', output_dir=Path('/tmp/test'),
        )
        with mock.patch.object(wrapper.subprocess, 'run', side_effect=subprocess.CalledProcessError(
            1, [], stderr='ERROR: SABR-only streaming experiment'
        )) as run, mock.patch.object(wrapper.logger, 'error'):
            self.assertFalse(dl._run_download(opts))
        self.assertEqual(run.call_count, 1 + len(wrapper.YOUTUBE_FALLBACK_CLIENTS))
        for call in run.call_args_list:
            self.assertFalse(any('formats=duplicate' in arg for arg in call.args[0]))


if __name__ == "__main__":
    unittest.main()
