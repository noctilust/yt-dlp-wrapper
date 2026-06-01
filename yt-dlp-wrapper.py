#!/usr/bin/env python3

"""
Optimized multi-platform video downloader wrapper for yt-dlp.
Supports YouTube, X (Twitter), and other platforms with improved error handling,
performance, and maintainability.
"""

import argparse
import json
import logging
import re
import shlex
import shutil
import socket
import subprocess
import sys
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

# YouTube client options for handling SABR streaming issues
YOUTUBE_CLIENTS = [
    'web',       # Web client (May use SABR streaming if enabled for your region/account)
    'android',   # Android client (Often still provides traditional formats)
    'tv',        # TV client (Often still provides traditional formats, may require login as of Jan 2026)
    'tv_downgraded',  # TV client with downgraded version (prevents SABR on logged-in accounts)
    'mweb',      # Mobile web client (recommended with PO Token for problematic videos)
    'web_embedded',  # Web embedded client (added 2026.01.31, fixed in 2026.03.13)
    'web_safari',    # Safari web client (added in yt-dlp 2026.03.13)
    'web_creator',   # Creator web client (added in yt-dlp 2026.03.13)
    'android_vr',    # Android VR client (fixed in yt-dlp 2026.03.13)
    'web_music', # Music web client
    'android_music'  # Music android client
]

SUPPORTED_PLATFORMS = {
    'youtube': ['youtube.com', 'youtu.be'],
    'x': ['twitter.com', 'x.com'],
    'other': []
}

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class YtDlpWrapperError(Exception):
    """Custom exception for wrapper-specific errors."""
    pass


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
    BROWSER_YT_DLP_MAP = {
        'firefox': 'firefox',
        'chrome': 'chrome',
        'safari': 'safari',
    }

    def __init__(self, cookies_browser: str = 'chrome'):
        self.cookies_browser = cookies_browser
        self.cookies_browser_arg = self._get_ytdlp_browser_arg(cookies_browser)
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are available."""
        # Check Python version (3.10+ required as of yt-dlp 2025.10.22)
        if sys.version_info < (3, 10):
            raise YtDlpWrapperError(
                f"Python 3.10+ required (you have {sys.version_info.major}.{sys.version_info.minor}). "
                "Please upgrade Python."
            )

        if not shutil.which('yt-dlp'):
            raise YtDlpWrapperError(
                "yt-dlp not found. Install with: uv pip install -U yt-dlp"
            )

        # Check yt-dlp version (2025.11.12 minimum for JS runtime support)
        version_cmd = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True, text=True, timeout=10
        )
        if version_cmd.returncode == 0:
            version_str = version_cmd.stdout.strip()
            try:
                from packaging.version import Version
                min_version = Version('2025.11.12')
                current_version = Version(version_str)
                if current_version < min_version:
                    logger.warning(
                        f"yt-dlp {version_str} detected; 2025.11.12+ recommended for full YouTube support. "
                        "Upgrade with: uv pip install -U yt-dlp"
                    )
            except Exception:
                pass  # Version parsing failed, skip check

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

    def _get_ytdlp_browser_arg(self, browser: str) -> str:
        """Get the yt-dlp --cookies-from-browser value for a wrapper browser name."""
        mapping = self.BROWSER_YT_DLP_MAP.get(browser, browser)
        if isinstance(mapping, dict):
            platform = 'darwin' if sys.platform == 'darwin' else 'linux'
            return mapping.get(platform, browser)
        return mapping

    def _resolve_browser(self, preferred: str) -> str:
        """Resolve the browser to use, falling back through the list if needed."""
        if self._is_browser_available(preferred):
            self.cookies_browser_arg = self._get_ytdlp_browser_arg(preferred)
            return preferred

        logger.warning(f"{preferred} not found, trying fallback browsers...")
        for browser in self.BROWSER_FALLBACK_ORDER:
            if browser != preferred and self._is_browser_available(browser):
                logger.info(f"Using {browser} for cookie extraction")
                self.cookies_browser_arg = self._get_ytdlp_browser_arg(browser)
                return browser

        logger.warning("No supported browser found. Downloads may fail for authenticated content.")
        self.cookies_browser_arg = self._get_ytdlp_browser_arg(preferred)
        return preferred

    def _check_javascript_runtime(self) -> Optional[str]:
        """Check for available JavaScript runtime for YouTube downloads."""
        # Runtimes in priority order (only deno is enabled by default in yt-dlp)
        runtimes = {
            'deno': '2.0.0+',
            'node': '20.0.0+ (25+ preferred)',
            'bun': '1.0.31+',
            'quickjs': '2023-12-9+'
        }

        for runtime, version in runtimes.items():
            if shutil.which(runtime):
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
                "   Alternatively: Node.js 20+, Bun, or QuickJS"
            )

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video metadata (including the full formats list) as JSON."""
        cmd = ['yt-dlp', '--cookies-from-browser', self.cookies_browser_arg, '-j', url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.warning(f"Could not retrieve video information: {result.stderr}")
                return {}
            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("Video info command timed out after 5 minutes")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse video information: {e}")
            return {}
    
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

    def download_video(self, url: str, extra_args: Optional[List[str]] = None,
                      format_selector: Optional[str] = None,
                      youtube_client: Optional[str] = None,
                      try_sabr: bool = False,
                      try_fallback_clients: bool = False,
                      prefer_premium: bool = True,
                      sponsorblock_mark: Optional[str] = None,
                      sponsorblock_remove: Optional[str] = None,
                      embed_chapters: bool = False,
                      sleep_interval: Optional[int] = None,
                      sleep_subtitles: Optional[float] = None,
                      pot_provider_mode: Optional[str] = None,
                      pot_provider_url: Optional[str] = None,
                      pot_provider_script: Optional[str] = None) -> bool:
        """Download video using yt-dlp with optimized settings."""
        if extra_args is None:
            extra_args = []

        # Detect platform
        platform = self.detect_platform(url)
        logger.info(f"Detected platform: {platform.capitalize()}")

        # Validate YouTube requirements (JavaScript runtime)
        self._validate_youtube_requirements(url)

        # Validate and configure PO Token provider for YouTube
        self._validate_pot_provider(url, pot_provider_mode)

        # Get video metadata (single -j call; also returns the formats list)
        logger.info("Fetching video metadata...")
        info = self.get_video_info(url)

        # Fail fast if metadata fetch failed — otherwise the output dir defaults
        # to "YYYY.MM.DD - video" and consecutive failed downloads collide.
        if not info:
            raise YtDlpWrapperError(
                f"Could not fetch video metadata for {url}. "
                "Check your cookies, network, and yt-dlp installation."
            )

        # Check for premium formats if YouTube and prefer_premium is enabled
        if platform == 'youtube' and prefer_premium and not format_selector:
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

        return self._run_download(
            url=url,
            extra_args=extra_args,
            format_selector=format_selector,
            youtube_client=youtube_client,
            try_sabr=try_sabr,
            try_fallback_clients=try_fallback_clients,
            sponsorblock_mark=sponsorblock_mark,
            sponsorblock_remove=sponsorblock_remove,
            embed_chapters=embed_chapters,
            sleep_interval=sleep_interval,
            sleep_subtitles=sleep_subtitles,
            pot_provider_mode=pot_provider_mode,
            pot_provider_url=pot_provider_url,
            pot_provider_script=pot_provider_script,
            platform=platform,
            output_dir=output_dir,
        )

    def _build_command(self, url: str, extra_args: List[str], format_selector: str,
                      youtube_client: Optional[str], try_sabr: bool,
                      sponsorblock_mark: Optional[str], sponsorblock_remove: Optional[str],
                      embed_chapters: bool, sleep_interval: Optional[int],
                      sleep_subtitles: Optional[float], pot_provider_mode: Optional[str],
                      pot_provider_url: Optional[str], pot_provider_script: Optional[str],
                      platform: str, output_dir: Path) -> List[str]:
        """Build the yt-dlp command list for a single download attempt."""
        base_cmd = [
            'yt-dlp',
            '--cookies-from-browser', self.cookies_browser_arg,
            '-f', format_selector,
            '--write-auto-sub',
            '--sub-lang', 'en.*',
            '--convert-subs', 'srt',
            '--ignore-errors',  # Continue on subtitle download errors
            '-P', str(output_dir),
            '--no-mtime',  # Don't set file modification time
            '--embed-metadata',  # Embed metadata in video file
        ]

        # Add chapter embedding (split from metadata for granular control)
        if embed_chapters:
            base_cmd.append('--embed-chapters')

        # Add SponsorBlock options (YouTube only)
        if platform == 'youtube':
            if sponsorblock_mark:
                base_cmd.extend(['--sponsorblock-mark', sponsorblock_mark])
                logger.info(f"SponsorBlock: Marking categories: {sponsorblock_mark}")
            if sponsorblock_remove:
                base_cmd.extend(['--sponsorblock-remove', sponsorblock_remove])
                logger.info(f"SponsorBlock: Removing categories: {sponsorblock_remove}")

        # Add sleep interval for rate limiting
        if sleep_interval:
            base_cmd.extend(['--sleep-interval', str(sleep_interval)])
            logger.info(f"Rate limiting: {sleep_interval} seconds between downloads")

        # Add sleep subtitles for subtitle download rate limiting
        if sleep_subtitles:
            base_cmd.extend(['--sleep-subtitles', str(sleep_subtitles)])
            logger.info(f"Subtitle rate limiting: {sleep_subtitles} seconds between subtitle downloads")

        # Add YouTube client option if specified and it's a YouTube URL
        if platform == 'youtube':
            # Handle YouTube SABR streaming format options
            if youtube_client:
                logger.info(f"Using YouTube client: {youtube_client}")
                base_cmd.extend(['--extractor-args', f"youtube:player-client={youtube_client}"])

            # Enable SABR formats if requested
            if try_sabr:
                logger.info("Enabling YouTube SABR format support")
                formats_arg = "youtube:formats=duplicate"
                if any(arg.startswith("--extractor-args") for arg in base_cmd):
                    # Update existing extractor args
                    for i, arg in enumerate(base_cmd):
                        if arg.startswith("youtube:player-client="):
                            base_cmd[i] = f"{arg};{formats_arg}"
                            break
                else:
                    # Add new extractor args
                    base_cmd.extend(['--extractor-args', formats_arg])

            # Configure PO Token provider if custom settings are provided
            pot_args = []
            if pot_provider_url:
                pot_args.append(f"youtubepot-bgutilhttp:base_url={pot_provider_url}")
                logger.info(f"Using custom PO Token provider URL: {pot_provider_url}")
            if pot_provider_script:
                pot_args.append(f"youtubepot-bgutilscript:script_path={pot_provider_script}")
                logger.info(f"Using custom PO Token provider script: {pot_provider_script}")

            if pot_args:
                # Combine with existing extractor args
                existing_yt_args = None
                for i, arg in enumerate(base_cmd):
                    if i > 0 and base_cmd[i-1] == '--extractor-args' and 'youtube' in arg:
                        existing_yt_args = i
                        break

                for pot_arg in pot_args:
                    if existing_yt_args is not None:
                        # Append to existing YouTube extractor args
                        base_cmd[existing_yt_args] = f"{base_cmd[existing_yt_args]};{pot_arg}"
                    else:
                        # Add new extractor args
                        base_cmd.extend(['--extractor-args', pot_arg])

        # Add extra arguments
        base_cmd.extend(extra_args)
        base_cmd.append(url)
        return base_cmd

    def _run_download(self, url: str, extra_args: List[str], format_selector: str,
                     youtube_client: Optional[str], try_sabr: bool,
                     try_fallback_clients: bool,
                     sponsorblock_mark: Optional[str], sponsorblock_remove: Optional[str],
                     embed_chapters: bool, sleep_interval: Optional[int],
                     sleep_subtitles: Optional[float], pot_provider_mode: Optional[str],
                     pot_provider_url: Optional[str], pot_provider_script: Optional[str],
                     platform: str, output_dir: Path) -> bool:
        """
        Run a single download attempt, optionally recursing into fallback clients on failure.

        This is the *only* method that calls subprocess.run for the actual download.
        Recursive fallback calls re-enter this method (not download_video) so the
        validation and metadata fetch from the outer call are reused.
        """
        base_cmd = self._build_command(
            url=url,
            extra_args=extra_args,
            format_selector=format_selector,
            youtube_client=youtube_client,
            try_sabr=try_sabr,
            sponsorblock_mark=sponsorblock_mark,
            sponsorblock_remove=sponsorblock_remove,
            embed_chapters=embed_chapters,
            sleep_interval=sleep_interval,
            sleep_subtitles=sleep_subtitles,
            pot_provider_mode=pot_provider_mode,
            pot_provider_url=pot_provider_url,
            pot_provider_script=pot_provider_script,
            platform=platform,
            output_dir=output_dir,
        )

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
                "only SABR formats"]):
                sabr_related = True
                if not po_token_error:  # Don't duplicate warnings
                    logger.warning("YouTube SABR streaming issue detected")

            # Try fallback clients for YouTube if enabled and appropriate
            if platform == 'youtube' and try_fallback_clients and (sabr_related or not youtube_client):
                available_clients = [c for c in YOUTUBE_CLIENTS if c != youtube_client]

                for client in available_clients:
                    logger.info(f"Trying fallback YouTube client: {client}")
                    # Create new extra_args without any existing YouTube client or format settings
                    filtered_args = [arg for arg in extra_args if "--extractor-args" not in arg]

                    # Try with this client (recurse into _run_download, NOT download_video)
                    if self._run_download(
                        url=url,
                        extra_args=filtered_args,
                        format_selector=format_selector,
                        youtube_client=client,
                        try_sabr=False,  # Don't try SABR in fallback attempt
                        try_fallback_clients=False,  # Prevent infinite recursion
                        sponsorblock_mark=sponsorblock_mark,
                        sponsorblock_remove=sponsorblock_remove,
                        embed_chapters=embed_chapters,
                        sleep_interval=sleep_interval,
                        sleep_subtitles=sleep_subtitles,
                        pot_provider_mode=pot_provider_mode,
                        pot_provider_url=pot_provider_url,
                        pot_provider_script=pot_provider_script,
                        platform=platform,
                        output_dir=output_dir,
                    ):
                        return True

                # If SABR might be the only option, try enabling it
                if sabr_related and not try_sabr:
                    logger.info("Trying with SABR format support enabled")
                    filtered_args = [arg for arg in extra_args if "--extractor-args" not in arg]

                    return self._run_download(
                        url=url,
                        extra_args=filtered_args,
                        format_selector=format_selector,
                        youtube_client=youtube_client or 'web',  # Default to web for SABR
                        try_sabr=True,  # Enable SABR formats
                        try_fallback_clients=False,  # Prevent infinite recursion
                        sponsorblock_mark=sponsorblock_mark,
                        sponsorblock_remove=sponsorblock_remove,
                        embed_chapters=embed_chapters,
                        sleep_interval=sleep_interval,
                        sleep_subtitles=sleep_subtitles,
                        pot_provider_mode=pot_provider_mode,
                        pot_provider_url=pot_provider_url,
                        pot_provider_script=pot_provider_script,
                        platform=platform,
                        output_dir=output_dir,
                    )

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
    parser.add_argument('--enable-sabr', action='store_true',
                       help='Enable YouTube SABR streaming format support')
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
        success = downloader.download_video(
            args.url,
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
            pot_provider_script=args.pot_provider_script
        )
        
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
