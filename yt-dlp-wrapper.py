#!/usr/bin/env python3

"""
Optimized multi-platform video downloader wrapper for yt-dlp.
Supports YouTube, X (Twitter), and other platforms with improved error handling,
performance, and maintainability.
"""

import os
import shutil
import subprocess
import sys

# Minimum Python version required by current yt-dlp releases (3.11 since 2026.10.26).
MIN_PYTHON_VERSION = (3, 11)
MIN_PYTHON_VERSION_TEXT = f'{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}'


def _ensure_supported_python():
    """Re-launch with an installed modern Python when the shebang finds an old one."""
    if sys.version_info >= MIN_PYTHON_VERSION:
        return
    for name in ('python3.14', 'python3.13', 'python3.12', 'python3.11', 'python'):
        executable = shutil.which(name)
        if not executable:
            continue
        try:
            probe = subprocess.run(
                [executable, '-c', f'import sys; sys.exit(sys.version_info < {MIN_PYTHON_VERSION})'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
            )
            if probe.returncode == 0:
                os.execv(executable, [executable, os.path.abspath(__file__), *sys.argv[1:]])
        except (OSError, subprocess.TimeoutExpired):
            continue
    sys.exit(f'Python {MIN_PYTHON_VERSION_TEXT}+ required. '
             'Install a supported Python and make it available on PATH.')


if __name__ == '__main__':
    _ensure_supported_python()

import argparse
import dataclasses
import glob
import json
import logging
import re
import shlex
import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# Configuration constants
DEFAULT_FORMAT_SELECTOR = (
    "bestvideo[height<=2160][vcodec~='^(av01|vp9|avc1)']+bestaudio/"
    "bestvideo[height<=1440][vcodec~='^(av01|vp9|avc1)']+bestaudio/"
    "bestvideo[height<=1080][vcodec~='^(av01|vp9|avc1)']+bestaudio/"
    "bestvideo[height<=720][vcodec~='^(av01|vp9|avc1)']+bestaudio/"
    "best[ext=mp4]/best"
)

# Supported clients as of yt-dlp 2026.10.26. Keep the initial attempt on
# yt-dlp's own defaults so it can choose clients based on authentication.
RECOMMENDED_YTDLP_VERSION = '2026.10.26'
YOUTUBE_CLIENTS = [
    'default', 'web', 'android', 'tv', 'tv_downgraded', 'tv_samsung', 'mweb',
    'web_embedded', 'web_safari', 'web_creator', 'android_vr', 'web_music',
    'visionos', 'ios', 'tv_simply',
]
# Prefer cookie-capable clients for retries; android_vr remains manual-only
# because upstream reports HTTP 403 errors for all of its formats.
YOUTUBE_FALLBACK_CLIENTS = [
    'web_embedded', 'tv_samsung', 'tv_downgraded', 'web_creator', 'web', 'mweb',
    'web_safari', 'web_music', 'tv', 'visionos', 'android', 'ios', 'tv_simply',
]

SUPPORTED_PLATFORMS = {
    'youtube': ['youtube.com', 'youtu.be'],
    'x': ['twitter.com', 'x.com'],
    'other': []
}
YOUTUBE_REMOTE_COMPONENT_ARGS = ['--remote-components', 'ejs:github']

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class YtDlpWrapperError(Exception):
    """Custom exception for wrapper-specific errors."""
    pass


@dataclass
class DownloadOptions:
    """All knobs that influence a single download.

    User-facing options (filled in from argparse); platform and output_dir
    are populated by ``download_video`` before the first call into
    ``_run_download`` / ``_build_command``.
    """
    url: str
    extra_args: List[str] = field(default_factory=list)
    format_selector: Optional[str] = None
    youtube_client: Optional[str] = None
    try_sabr: bool = False
    try_fallback_clients: bool = False
    prefer_premium: bool = True
    sponsorblock_mark: Optional[str] = None
    sponsorblock_remove: Optional[str] = None
    embed_chapters: bool = False
    sleep_interval: Optional[int] = None
    sleep_subtitles: Optional[float] = None
    pot_provider_mode: Optional[str] = None
    pot_provider_url: Optional[str] = None
    pot_provider_script: Optional[str] = None
    # Populated by download_video:
    platform: Optional[str] = None
    output_dir: Optional[Path] = None


class VideoDownloader:
    """Main class for handling video downloads with yt-dlp."""
    
    BROWSER_FALLBACK_ORDER = ['chrome', 'firefox', 'safari']
    BROWSER_PATHS = {
        'firefox': [
            '/Applications/Firefox.app',
            '~/.mozilla/firefox',
            '/usr/bin/firefox'
        ],
        'chrome': [
            '/Applications/Google Chrome.app',
            '~/Library/Application Support/Google/Chrome',
            '~/.config/google-chrome'
        ],
        'safari': [
            '/Applications/Safari.app'
        ]
    }
    # Cookie databases yt-dlp can read for each browser. A readable file here
    # is the real prerequisite; the install directory alone proves nothing
    # (macOS TCC can block reads below ~/Library/Application Support).
    COOKIE_DB_GLOBS = {
        'chrome': [
            '~/Library/Application Support/Google/Chrome/*/Cookies',
            '~/Library/Application Support/Google/Chrome/*/Network/Cookies',
            '~/.config/google-chrome/*/Cookies',
            '~/.config/google-chrome/*/Network/Cookies',
            '~/.config/chromium/*/Cookies',
            '~/.config/chromium/*/Network/Cookies',
        ],
        'firefox': [
            '~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite',
            '~/.mozilla/firefox/*/cookies.sqlite',
            '~/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite',
        ],
        'safari': [
            '~/Library/Cookies/Cookies.binarycookies',
            '~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies',
        ],
    }

    def __init__(self, cookies_browser: str = 'chrome'):
        self.cookies_browser = cookies_browser
        self.cookies_browser_arg: Optional[str] = cookies_browser
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are available."""
        # Check Python version (current yt-dlp requires it)
        if sys.version_info < MIN_PYTHON_VERSION:
            raise YtDlpWrapperError(
                f"Python {MIN_PYTHON_VERSION_TEXT}+ required "
                f"(you have {sys.version_info.major}.{sys.version_info.minor}). "
                "Please upgrade Python."
            )

        if not shutil.which('yt-dlp'):
            raise YtDlpWrapperError(
                "yt-dlp not found. Install with: uv pip install -U yt-dlp"
            )

        # Use the CLI's version, without requiring the packaging library.
        version_cmd = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True, text=True, timeout=10
        )
        if version_cmd.returncode == 0:
            version_str = version_cmd.stdout.strip()
            version_match = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})(?:\D|$)', version_str)
            recommended_version = tuple(map(int, RECOMMENDED_YTDLP_VERSION.split('.')))
            if version_match and tuple(map(int, version_match.groups())) < recommended_version:
                logger.warning(
                    f"yt-dlp {version_str} detected; {RECOMMENDED_YTDLP_VERSION}+ recommended "
                    "for current YouTube clients. Upgrade with: uv pip install -U 'yt-dlp[default]'"
                )

        # Check ffmpeg (required for subtitle conversion and video merging)
        if not shutil.which('ffmpeg'):
            logger.warning(
                "⚠️  ffmpeg not found. Subtitles will not be converted to SRT, "
                "and video/audio merging will fail. Install with: brew install ffmpeg"
            )

        # Check if browser is available for cookie extraction, with failover
        self.cookies_browser = self._resolve_browser(self.cookies_browser)

    def _is_browser_available(self, browser: str) -> bool:
        """Check if a browser is installed by looking for known paths."""
        paths = self.BROWSER_PATHS.get(browser, [])
        return any(Path(p).expanduser().exists() for p in paths)

    def _has_readable_cookies(self, browser: str) -> bool:
        """Check that yt-dlp can actually read this browser's cookie database."""
        for pattern in self.COOKIE_DB_GLOBS.get(browser, []):
            for db_path in glob.glob(os.path.expanduser(pattern)):
                try:
                    with open(db_path, 'rb') as db:
                        if db.read(16):
                            return True
                except OSError:
                    continue
        return False

    def _resolve_browser(self, preferred: str) -> Optional[str]:
        """Resolve a browser for cookie extraction, or None when none is usable.

        A browser only qualifies when it is installed *and* its cookie database
        is readable. Passing an unreadable database to ``--cookies-from-browser``
        makes yt-dlp abort before extraction, so cookies are skipped instead and
        public videos still download.
        """
        candidates = [preferred, *(b for b in self.BROWSER_FALLBACK_ORDER if b != preferred)]
        installed_but_unreadable = []
        for browser in candidates:
            if not self._is_browser_available(browser):
                continue
            if self._has_readable_cookies(browser):
                if browser != preferred:
                    logger.info(f"Using {browser} for cookie extraction")
                self.cookies_browser_arg = browser
                return browser
            installed_but_unreadable.append(browser)

        if installed_but_unreadable:
            logger.warning(
                f"Cookie database not readable for: {', '.join(installed_but_unreadable)}. "
                "Continuing without cookies; authenticated videos may fail. "
                "Grant Full Disk Access to your terminal (System Settings → Privacy & Security → "
                "Full Disk Access) or pass --cookies <cookies.txt>."
            )
        else:
            logger.warning(
                f"None of the supported browsers ({', '.join(candidates)}) found. "
                "Continuing without cookies; authenticated content may fail."
            )
        self.cookies_browser_arg = None
        return None

    def _check_javascript_runtime(self) -> Optional[str]:
        """Check for available JavaScript runtime for YouTube downloads."""
        # Match yt-dlp priority and executable names. yt-dlp validates versions.
        runtimes = {
            'deno': 'deno',
            'node': 'node',
            'quickjs': 'qjs',
            'bun': 'bun',
        }

        for runtime, executable in runtimes.items():
            if shutil.which(executable):
                logger.debug(f"Found JavaScript runtime: {runtime}")
                return runtime

        return None

    def _check_pot_plugin_installed(self) -> bool:
        """Check if bgutil-ytdlp-pot-provider plugin is installed."""
        try:
            import importlib.util
            installed = importlib.util.find_spec("bgutil_ytdlp_pot_provider") is not None
            if installed:
                logger.debug("PO Token provider plugin is installed")
            return installed
        except (ImportError, ModuleNotFoundError, ValueError) as e:
            # find_spec can raise ValueError for names without a parent package
            logger.debug(f"Could not check PO Token plugin: {e}")
            return False

    def _check_pot_server_running(self, host: str = '127.0.0.1', port: int = 4416, timeout: float = 1.0) -> bool:
        """Check if the PO Token HTTP server is running."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                logger.debug(f"PO Token HTTP server is running at {host}:{port}")
                return True
            return False
        except Exception as e:
            logger.debug(f"PO Token HTTP server check failed: {e}")
            return False

    def _validate_pot_provider(self, url: str, pot_provider_mode: Optional[str] = None) -> None:
        """
        Validate PO Token provider setup for YouTube downloads.
        Logs informational messages and warnings; does not return any value.
        Actual extractor args are built inline in download_video() from pot_provider_url/script.
        """
        if self.detect_platform(url) != 'youtube':
            return

        # Check if plugin is installed
        plugin_installed = self._check_pot_plugin_installed()

        if not plugin_installed:
            logger.info(
                "💡 Tip: Install bgutil-ytdlp-pot-provider to bypass YouTube's bot detection:\n"
                "   uv pip install bgutil-ytdlp-pot-provider\n"
                "   See: https://github.com/Brainicism/bgutil-ytdlp-pot-provider"
            )
            return

        # Plugin is installed, check which mode to use
        if pot_provider_mode == 'script':
            logger.info("Using PO Token provider in script mode")
            return  # Script mode uses default plugin behavior

        # Default to HTTP server mode
        server_running = self._check_pot_server_running()

        if server_running:
            logger.info("✓ PO Token provider HTTP server detected and ready")
        else:
            logger.warning(
                "⚠️  PO Token provider plugin installed but HTTP server not detected.\n"
                "   Start the server with Docker:\n"
                "     docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider\n"
                "   Or use Node.js (see: https://github.com/Brainicism/bgutil-ytdlp-pot-provider)\n"
                "   Alternatively, use --pot-provider-mode script (slower but no server needed)"
            )

    def _validate_youtube_requirements(self, url: str) -> None:
        """Validate YouTube-specific requirements like JavaScript runtime."""
        if self.detect_platform(url) != 'youtube':
            return

        runtime = self._check_javascript_runtime()
        if not runtime:
            logger.warning(
                "⚠️  No JavaScript runtime detected. YouTube downloads may have limited format availability.\n"
                "   As of yt-dlp 2025.11.12, a JavaScript runtime is required for full YouTube support.\n"
                "   Install Deno (recommended): https://deno.land/\n"
                "   - macOS: brew install deno\n"
                "   - Linux: curl -fsSL https://deno.land/install.sh | sh\n"
                "   - Windows: irm https://deno.land/install.ps1 | iex\n"
                "   Alternatively: Node.js 22+, Bun (deprecated), or QuickJS"
            )

    def _build_extraction_args(self, opts: DownloadOptions) -> List[str]:
        """Settings shared by metadata extraction and the actual download."""
        cmd = []
        if self.cookies_browser_arg:
            cmd.extend(['--cookies-from-browser', self.cookies_browser_arg])
        if self.detect_platform(opts.url) != 'youtube':
            return cmd

        cmd.extend(YOUTUBE_REMOTE_COMPONENT_ARGS)
        # Deno is already enabled by yt-dlp. Enable an installed alternative
        # unless the user explicitly controls the runtime list.
        if not any(arg.split('=', 1)[0] in ('--js-runtimes', '--no-js-runtimes')
                   for arg in opts.extra_args):
            runtime = self._check_javascript_runtime()
            if runtime and runtime != 'deno':
                cmd.extend(['--js-runtimes', runtime])

        youtube_args = []
        if opts.youtube_client:
            youtube_args.append(f'player-client={opts.youtube_client}')
        if opts.try_sabr:
            # Historical --enable-sabr flag: duplicate URLs/protocols are
            # exposed by this setting, but SABR streams are still skipped.
            youtube_args.append('formats=duplicate')
        if youtube_args:
            cmd.extend(['--extractor-args', 'youtube:' + ';'.join(youtube_args)])

        # Each provider has its own extractor namespace.
        if opts.pot_provider_url:
            cmd.extend(['--extractor-args', f'youtubepot-bgutilhttp:base_url={opts.pot_provider_url}'])
        if opts.pot_provider_script:
            cmd.extend(['--extractor-args', f'youtubepot-bgutilscript:script_path={opts.pot_provider_script}'])
        return cmd

    @staticmethod
    def _metadata_extra_args(extra_args: List[str]) -> List[str]:
        """Forward extraction controls without download/output side effects."""
        value_options = {
            '--js-runtimes', '--remote-components', '--extractor-args',
            '--cookies-from-browser', '--cookies', '--proxy', '--impersonate',
            '--source-address', '--socket-timeout', '--config-locations',
            '--plugin-dirs', '--cache-dir', '--extractor-retries', '--retries',
        }
        flag_options = {
            '--no-js-runtimes', '--no-remote-components', '--no-cookies',
            '--no-cookies-from-browser', '--no-playlist', '--ignore-config',
            '--no-plugin-dirs', '--force-ipv4', '--force-ipv6',
            '--no-cache-dir',
        }
        forwarded = []
        args = iter(extra_args)
        for arg in args:
            option, equals, _ = arg.partition('=')
            if option in value_options:
                forwarded.append(arg)
                if not equals:
                    value = next(args, None)
                    if value is not None:
                        forwarded.append(value)
            elif option in flag_options:
                forwarded.append(arg)
        return forwarded

    @staticmethod
    def _fallback_extra_args(extra_args: List[str], client: str) -> List[str]:
        """Replace a pass-through client while retaining other extractor settings."""
        def replace_client(value: str) -> str:
            namespace, colon, settings = value.partition(':')
            if not colon or namespace.lower() != 'youtube':
                return value
            settings = [setting for setting in settings.split(';')
                        if setting.split('=', 1)[0].strip().replace('-', '_') != 'player_client']
            return 'youtube:' + ';'.join([*settings, f'player-client={client}'])

        forwarded = []
        args = iter(extra_args)
        for arg in args:
            if arg == '--extractor-args':
                forwarded.append(arg)
                value = next(args, None)
                if value is not None:
                    forwarded.append(replace_client(value))
            elif arg.startswith('--extractor-args='):
                forwarded.append('--extractor-args=' + replace_client(arg.split('=', 1)[1]))
            else:
                forwarded.append(arg)
        return forwarded

    def get_video_info(self, url: str, opts: Optional[DownloadOptions] = None) -> Dict[str, Any]:
        """Get video metadata (including the full formats list) as JSON.

        Raises YtDlpWrapperError if the fetch fails, times out, or returns
        unparseable output — callers don't have to handle empty-dict results.
        """
        opts = opts or DownloadOptions(url=url)
        cmd = ['yt-dlp', *self._build_extraction_args(opts)]
        cmd.extend(self._metadata_extra_args(opts.extra_args))
        # Still return metadata when no formats exist, so download retries can
        # select another client. Explicit simulation keeps config files from
        # turning the metadata probe into a download.
        cmd.extend(['--simulate', '--ignore-no-formats-error', '-j', url])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise YtDlpWrapperError(
                f"Video info command timed out after 5 minutes for {url}"
            )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise YtDlpWrapperError(
                f"Could not retrieve video information for {url}: {stderr}"
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise YtDlpWrapperError(
                f"Could not parse video information for {url}: {e}"
            )
    
    def detect_platform(self, url: str) -> str:
        """Detect the platform from the URL."""
        from urllib.parse import urlparse
        hostname = (urlparse(url).hostname or '').lower()
        for platform, domains in SUPPORTED_PLATFORMS.items():
            if any(hostname == domain or hostname.endswith('.' + domain) for domain in domains):
                return platform
        return 'other'
    
    def create_output_dir(self, title: str, date_str: Optional[str] = None) -> Path:
        """Create an output directory based on video title and date."""
        # Format date
        if date_str:
            try:
                date_fmt = datetime.strptime(date_str, '%Y%m%d').strftime('%Y.%m.%d')
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}")
                date_fmt = datetime.now().strftime('%Y.%m.%d')
        else:
            date_fmt = datetime.now().strftime('%Y.%m.%d')

        # Clean title for filesystem compatibility:
        #   - strip path separators and reserved chars (cross-platform)
        #   - strip ASCII control chars
        #   - strip leading/trailing whitespace and dots (problematic on macOS/Windows)
        #   - truncate to 100 chars
        #   - re-strip after slicing in case the slice landed on a separator
        clean_title = re.sub(r'[\\/:*?\"<>|\x00-\x1f]', '', title)
        clean_title = clean_title.strip().strip('. ')
        clean_title = clean_title[:100].strip().strip('. ')

        folder_name = f"{date_fmt} - {clean_title}"
        output_dir = Path.home() / "Downloads" / folder_name

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise YtDlpWrapperError(f"Could not create output directory: {e}")

        return output_dir
    
    def find_premium_format(self, info: Dict[str, Any]) -> Optional[str]:
        """
        Pick the best Premium format from a video info dict.

        Reads the `formats` list already returned by `yt-dlp -j` instead of running
        a second `yt-dlp -F` invocation. Matches against `format_note` (e.g.
        "1080p Premium") and selects the format with the highest `height`.
        """
        formats = info.get('formats') or []
        best_format_id = None
        best_height = 0

        for fmt in formats:
            if not isinstance(fmt, dict):
                continue
            if 'Premium' not in str(fmt.get('format_note') or ''):
                continue

            format_id = fmt.get('format_id')
            if format_id is None:
                continue

            height = int(fmt.get('height') or 0)
            if height > best_height:
                best_format_id = format_id
                best_height = height

        if not best_format_id:
            logger.info("No Premium formats found, using default format selector")
            return None

        logger.info(f"Best Premium format found: {best_format_id} with resolution height {best_height}px")
        return f"{best_format_id}+bestaudio/best"

    def download_video(self, opts: DownloadOptions) -> bool:
        """Download video using yt-dlp with optimized settings.

        Validates, fetches metadata, picks a format, and hands the work
        off to ``_run_download`` with platform + output_dir filled in.
        """
        # Detect platform
        platform = self.detect_platform(opts.url)
        logger.info(f"Detected platform: {platform.capitalize()}")

        # Validate YouTube requirements (JavaScript runtime)
        self._validate_youtube_requirements(opts.url)

        # Validate and configure PO Token provider for YouTube
        self._validate_pot_provider(opts.url, opts.pot_provider_mode)

        # Get video metadata (single -j call; also returns the formats list).
        # Raises YtDlpWrapperError on failure — download_video never sees an
        # empty info dict, so we don't have to guard against one.
        logger.info("Fetching video metadata...")
        info = self.get_video_info(opts.url, opts)

        # Check for premium formats if YouTube and prefer_premium is enabled
        format_selector = opts.format_selector
        if platform == 'youtube' and opts.prefer_premium and not format_selector:
            premium_format = self.find_premium_format(info)
            if premium_format:
                format_selector = premium_format
                logger.info(f"Using Premium format: {format_selector}")

        if format_selector is None:
            format_selector = DEFAULT_FORMAT_SELECTOR

        # Create output directory
        title = info.get('title', 'video')
        date_str = info.get('upload_date') or info.get('release_date')
        output_dir = self.create_output_dir(title, date_str)
        logger.info(f"Output directory: {output_dir}")

        run_opts = dataclasses.replace(
            opts,
            format_selector=format_selector,
            platform=platform,
            output_dir=output_dir,
        )
        return self._run_download(run_opts)

    def _build_command(self, opts: DownloadOptions) -> List[str]:
        """Build the yt-dlp command list for a single download attempt."""
        platform = opts.platform
        output_dir = opts.output_dir
        base_cmd = [
            'yt-dlp',
            *self._build_extraction_args(opts),
            '-f', opts.format_selector,
            '--write-auto-sub',
            '--sub-lang', 'en.*',
            '--convert-subs', 'srt',
            '--ignore-errors',  # Continue on subtitle download errors
            '-P', str(output_dir),
            '--no-mtime',  # Don't set file modification time
            '--embed-metadata',  # Embed metadata in video file
        ]

        # Add chapter embedding (split from metadata for granular control)
        if opts.embed_chapters:
            base_cmd.append('--embed-chapters')

        # Add SponsorBlock options (YouTube only)
        if platform == 'youtube':
            if opts.sponsorblock_mark:
                base_cmd.extend(['--sponsorblock-mark', opts.sponsorblock_mark])
                logger.info(f"SponsorBlock: Marking categories: {opts.sponsorblock_mark}")
            if opts.sponsorblock_remove:
                base_cmd.extend(['--sponsorblock-remove', opts.sponsorblock_remove])
                logger.info(f"SponsorBlock: Removing categories: {opts.sponsorblock_remove}")

        # Add sleep interval for rate limiting
        if opts.sleep_interval:
            base_cmd.extend(['--sleep-interval', str(opts.sleep_interval)])
            logger.info(f"Rate limiting: {opts.sleep_interval} seconds between downloads")

        # Add sleep subtitles for subtitle download rate limiting
        if opts.sleep_subtitles:
            base_cmd.extend(['--sleep-subtitles', str(opts.sleep_subtitles)])
            logger.info(f"Subtitle rate limiting: {opts.sleep_subtitles} seconds between subtitle downloads")

        # Add extra arguments
        base_cmd.extend(opts.extra_args)
        base_cmd.append(opts.url)
        return base_cmd

    def _run_download(self, opts: DownloadOptions) -> bool:
        """
        Run a single download attempt, optionally recursing into fallback clients on failure.

        This is the *only* method that calls subprocess.run for the actual download.
        Recursive fallback calls re-enter this method (not download_video) so the
        validation and metadata fetch from the outer call are reused.
        """
        base_cmd = self._build_command(opts)

        # Execute download.
        # stdout is inherited (so the user sees yt-dlp's progress in their terminal);
        # stderr is captured so SABR / PO Token error detection actually works.
        logger.info("Starting download...")
        try:
            subprocess.run(
                base_cmd,
                stdout=None,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=3600,  # 1 hour timeout
            )
            logger.info("Download completed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            error_output = e.stderr or ""
            platform = opts.platform

            # Check for PO Token errors
            po_token_error = False
            if platform == 'youtube' and any(phrase in error_output for phrase in [
                "PO Token", "po_token", "requires a GVS PO Token"]):
                po_token_error = True

                # Check if plugin is installed
                plugin_installed = self._check_pot_plugin_installed()

                if not plugin_installed:
                    logger.warning(
                        "⚠️  YouTube PO Token required.\n"
                        "   \n"
                        "   RECOMMENDED SOLUTION - Install PO Token provider plugin:\n"
                        "     uv pip install bgutil-ytdlp-pot-provider\n"
                        "   \n"
                        "   Then start the HTTP server with Docker:\n"
                        "     docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider\n"
                        "   \n"
                        "   This automates PO Token generation. See:\n"
                        "     https://github.com/Brainicism/bgutil-ytdlp-pot-provider\n"
                        "   \n"
                        "   Alternative: Try 'mweb' client: --youtube-client mweb"
                    )
                else:
                    logger.warning(
                        "⚠️  YouTube PO Token required but provider plugin failed.\n"
                        "   \n"
                        "   Make sure the HTTP server is running:\n"
                        "     docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider\n"
                        "   \n"
                        "   Or try script mode: --pot-provider-mode script\n"
                        "   Or try 'mweb' client: --youtube-client mweb"
                    )

            # Check if the error might be related to SABR streaming
            sabr_related = False
            if platform == 'youtube' and any(phrase in error_output for phrase in [
                "web client https formats require a GVS PO Token",
                "YouTube is forcing SABR streaming",
                "only SABR formats", "SABR-only streaming experiment"]):
                sabr_related = True
                if not po_token_error:  # Don't duplicate warnings
                    logger.warning("YouTube SABR streaming issue detected")

            # Try fallback clients for YouTube if enabled and appropriate
            if (platform == 'youtube' and opts.try_fallback_clients
                    and (sabr_related or po_token_error or not opts.youtube_client)):
                available_clients = [c for c in YOUTUBE_FALLBACK_CLIENTS if c != opts.youtube_client]

                for client in available_clients:
                    logger.info(f"Trying fallback YouTube client: {client}")
                    if self._run_download(dataclasses.replace(
                        opts,
                        youtube_client=client,
                        try_sabr=False,  # Don't try SABR in fallback attempt
                        try_fallback_clients=False,  # Prevent infinite recursion
                        extra_args=self._fallback_extra_args(opts.extra_args, client),
                    )):
                        return True

            logger.error(f"Download failed (return code {e.returncode}): {shlex.join(base_cmd)}")
            if e.stderr:
                logger.error(f"Error details: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Download timed out after 1 hour")
            return False


def main():
    """Main function to handle command line arguments and orchestrate the download."""
    parser = argparse.ArgumentParser(
        description='Download videos from YouTube, X (Twitter), and other platforms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.youtube.com/watch?v=VIDEO_ID"
  %(prog)s "https://twitter.com/user/status/TWEET_ID" --format "best[height<=720]"
        """
    )
    
    parser.add_argument('url', help='URL to download')
    parser.add_argument('--format', '-f', 
                       help='Custom format selector (overrides default)')
    parser.add_argument('--browser', '-b', default='chrome',
                       choices=['firefox', 'chrome', 'safari'],
                       help='Browser to extract cookies from (default: chrome)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--youtube-client', '-y', 
                       choices=YOUTUBE_CLIENTS,
                       help='YouTube client to use (helps with SABR streaming issues)')
    parser.add_argument('--include-duplicate-formats', '--enable-sabr', dest='enable_sabr', action='store_true',
                       help='Include duplicate YouTube formats (legacy alias: --enable-sabr; does not enable SABR)')
    parser.add_argument('--no-fallback', action='store_true',
                       help='Disable automatic fallback to other YouTube clients')
    parser.add_argument('--no-premium', action='store_true',
                       help='Disable automatic selection of Premium formats')
    parser.add_argument('--sponsorblock-mark', metavar='CATS',
                       help='SponsorBlock categories to mark as chapters (e.g., "all", "sponsor,intro,outro")')
    parser.add_argument('--sponsorblock-remove', metavar='CATS',
                       help='SponsorBlock categories to remove from video (e.g., "sponsor")')
    parser.add_argument('--embed-chapters', action='store_true',
                       help='Embed chapter markers in video file')
    parser.add_argument('--sleep-interval', type=int, metavar='SECONDS',
                       help='Sleep interval between downloads (recommended: 5-10 seconds)')
    parser.add_argument('--sleep-subtitles', type=float, metavar='SECONDS',
                       help='Sleep interval between subtitle downloads (accepts decimal values)')
    parser.add_argument('--format-sort-reset', action='store_true',
                       help='Reset format sorting preferences (useful with custom format selectors)')
    parser.add_argument('--compat-options', metavar='OPTS',
                       help='Compatibility options (e.g., "2025" for 2025 compatibility mode)')
    parser.add_argument('--pot-provider-mode', choices=['http', 'script'],
                       help='PO Token provider mode: http (default, requires server) or script (slower but no server)')
    parser.add_argument('--pot-provider-url', metavar='URL',
                       help='Custom PO Token provider HTTP server URL (default: http://127.0.0.1:4416)')
    parser.add_argument('--pot-provider-script', metavar='PATH',
                       help='Path to PO Token provider script (for script mode)')

    # Parse known and unknown args to allow passing through to yt-dlp
    args, extra_args = parser.parse_known_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Add format-sort-reset to extra_args if specified
    if args.format_sort_reset:
        extra_args.append('--format-sort-reset')

    # Add compat-options to extra_args if specified
    if args.compat_options:
        extra_args.extend(['--compat-options', args.compat_options])
    
    try:
        downloader = VideoDownloader(cookies_browser=args.browser)
        opts = DownloadOptions(
            url=args.url,
            extra_args=extra_args,
            format_selector=args.format,
            youtube_client=args.youtube_client,
            try_sabr=args.enable_sabr,
            try_fallback_clients=not args.no_fallback,
            prefer_premium=not args.no_premium,
            sponsorblock_mark=args.sponsorblock_mark,
            sponsorblock_remove=args.sponsorblock_remove,
            embed_chapters=args.embed_chapters,
            sleep_interval=args.sleep_interval,
            sleep_subtitles=args.sleep_subtitles,
            pot_provider_mode=args.pot_provider_mode,
            pot_provider_url=args.pot_provider_url,
            pot_provider_script=args.pot_provider_script,
        )
        success = downloader.download_video(opts)
        
        sys.exit(0 if success else 1)
        
    except YtDlpWrapperError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
