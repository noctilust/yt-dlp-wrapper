# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python wrapper script for [yt-dlp](https://github.com/yt-dlp/yt-dlp) that provides intelligent video downloading from YouTube, X (Twitter), and other platforms. The project consists of a single Python script (`yt-dlp-wrapper.py`) with no build system or testing framework.

## Key Components

### Main Script: `yt-dlp-wrapper.py`
- **VideoDownloader class**: Core functionality for downloading videos with advanced error handling
- **Platform detection**: Automatically detects YouTube, X/Twitter, or other platforms
- **Smart format selection**: Prioritizes 4K→2K→1080p→720p with codec preference (av01 > vp9 > avc1)
- **Premium format detection**: Automatically detects and uses YouTube Premium formats when available
- **SABR streaming support**: Handles YouTube's SABR streaming with client fallback mechanisms
- **PO Token provider integration**: Automatic detection and integration with bgutil-ytdlp-pot-provider plugin for bypassing YouTube bot detection
- **SponsorBlock integration**: Mark or remove sponsor segments, intros, outros, hooks, and other video sections
- **JavaScript runtime validation**: Checks for Deno/Node.js for YouTube downloads (required as of yt-dlp 2025.11.12)
- **Cookie extraction**: Supports Firefox, Chrome, Safari browsers for authenticated downloads
- **Comprehensive error handling**: Timeout protection, client fallbacks, PO Token detection, and graceful degradation
- **Output organization**: Creates dated folders in `~/Downloads/YYYY.MM.DD - <Video Title>/`

### Configuration Constants
- `DEFAULT_FORMAT_SELECTOR`: Complex format selector string prioritizing resolution and codec
- `YOUTUBE_CLIENTS`: Available YouTube client options (web, android, tv, tv_downgraded, mweb, web_music, android_music)
- `SUPPORTED_PLATFORMS`: Platform detection mapping for YouTube, X/Twitter

## Common Development Commands

### Running the Script
```bash
python yt-dlp-wrapper.py "https://www.youtube.com/watch?v=VIDEO_ID"
python yt-dlp-wrapper.py "URL" --browser chrome --format "best[height<=1080]" --verbose
python yt-dlp-wrapper.py "URL" --youtube-client android --enable-sabr
python yt-dlp-wrapper.py "URL" --no-premium --no-fallback
python yt-dlp-wrapper.py "URL" --sponsorblock-mark all --embed-chapters
python yt-dlp-wrapper.py "URL" --youtube-client mweb  # For PO Token issues
python yt-dlp-wrapper.py "URL" --sleep-interval 5  # Rate limiting for batch downloads
python yt-dlp-wrapper.py "URL" --pot-provider-mode script  # Use PO Token provider in script mode
python yt-dlp-wrapper.py "URL" --pot-provider-url "http://localhost:8080"  # Custom PO Token server
```

### Available Command Line Options
- `--format, -f`: Custom format selector (overrides default)
- `--browser, -b`: Browser for cookie extraction (firefox, chrome, safari)
- `--verbose, -v`: Enable debug logging
- `--youtube-client, -y`: Specific YouTube client (web, android, tv, tv_downgraded, mweb, web_music, android_music)
- `--enable-sabr`: Enable YouTube SABR streaming format support
- `--no-fallback`: Disable automatic fallback to other YouTube clients
- `--no-premium`: Disable automatic Premium format selection
- `--sponsorblock-mark CATS`: Mark SponsorBlock categories as chapters (e.g., "all", "sponsor,intro,outro,hook")
- `--sponsorblock-remove CATS`: Remove SponsorBlock categories from video (e.g., "sponsor")
- `--embed-chapters`: Embed chapter markers in video file
- `--sleep-interval SECONDS`: Sleep interval between downloads (recommended: 5-10 seconds for rate limiting)
- `--pot-provider-mode MODE`: PO Token provider mode (http or script)
- `--pot-provider-url URL`: Custom PO Token provider HTTP server URL (default: http://127.0.0.1:4416)
- `--pot-provider-script PATH`: Path to PO Token provider script (for script mode)

### Dependencies
- **Python 3.10+** required (enforced as of yt-dlp 2025.10.22)
- **yt-dlp** must be installed and in PATH: `uv pip install -U yt-dlp`
- **JavaScript runtime** (required for YouTube as of yt-dlp 2025.11.12):
  - **Deno** (recommended, enabled by default): `brew install deno` (macOS) or see https://deno.land/
  - Alternative runtimes: Node.js 20+, Bun 1.0.31+, or QuickJS 2023-12-9+
  - Without a runtime, YouTube downloads will have severely limited format availability
- **Browser** (Firefox, Chrome, or Safari) for cookie extraction and authenticated content
- **PO Token provider plugin** (optional but recommended for YouTube):
  - Install plugin: `uv pip install bgutil-ytdlp-pot-provider`
  - Start HTTP server with Docker: `docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider`
  - Or use Node.js setup (requires Node.js 18+): see https://github.com/Brainicism/bgutil-ytdlp-pot-provider
  - Automatically bypasses YouTube bot detection and PO Token requirements

### Testing
No formal testing framework is configured. Test manually with various video URLs from different platforms.

## Architecture Notes

### Command Line Interface
Uses `argparse` with `parse_known_args()` to forward unknown arguments directly to yt-dlp, enabling pass-through of additional yt-dlp options.

### Error Handling Strategy
- Custom `YtDlpWrapperError` exception for wrapper-specific errors
- Python version validation (3.10+ required)
- JavaScript runtime detection and warnings for YouTube downloads
- Timeout protection: 5 minutes for metadata, 1 hour for downloads
- YouTube client fallback system for SABR streaming issues
- PO Token error detection with helpful guidance (suggests mweb client)
- Graceful degradation when browser cookies unavailable
- Proper exit codes (0 for success, 1 for failure)

### Video Processing Flow
1. Validate dependencies (Python 3.10+, yt-dlp, browser availability)
2. Detect platform from URL
3. Validate YouTube requirements (JavaScript runtime check)
4. Validate PO Token provider setup (plugin and server detection)
5. Check for Premium formats (YouTube only, if enabled)
6. Extract video metadata with timeout protection
7. Create organized output directory with sanitized names
8. Build download command with appropriate client settings
9. Add SponsorBlock options (mark/remove categories) if specified
10. Add chapter embedding if requested
11. Add rate limiting (sleep interval) if specified
12. Configure PO Token provider extractor args if custom settings provided
13. Download video with optimized format selector
14. Handle SABR streaming and PO Token errors with client fallbacks
15. Download and convert subtitles to SRT with `--ignore-errors`
16. Embed metadata and chapters in video file

### Format Selection Logic
1. **Premium Detection**: Automatically detects and uses YouTube Premium formats (highest resolution available)
2. **Default Selector**: Uses regex-based format selector prioritizing:
   - Resolution: 4K (2160p) → 2K (1440p) → 1080p → 720p
   - Codec: av01 > vp9 > avc1 within each resolution
   - Fallback to best available format

### YouTube SABR Streaming & PO Token Handling
- **PO Token Provider Integration**: Automatically detects and uses bgutil-ytdlp-pot-provider plugin
  - Checks if plugin is installed and HTTP server is running
  - Provides helpful installation guidance if not detected
  - Supports custom server URLs and script mode via command-line options
  - Automatically configures extractor args for custom setups
- Detects SABR streaming errors ("web client https formats require a GVS PO Token")
- Detects PO Token errors and recommends plugin installation or mweb client
- Automatically tries fallback clients: android, tv, tv_downgraded, mweb, web_music, android_music
- Can enable SABR format support with `--enable-sabr` flag
- Prevents infinite recursion with fallback attempt limits
- **tv_downgraded**: Used by default for logged-in accounts, prevents SABR format issues
- **mweb**: Alternative for PO Token-related errors

### SponsorBlock Integration
- Mark sponsor segments, intros, outros, hooks, and other categories as chapters
- Remove unwanted segments from downloaded videos
- Available categories: sponsor, intro, outro, selfproto, preview, filler, interaction, music_offtopic, hook, poi_highlight, chapter, all
- **hook** category (added in yt-dlp 2025.11.12): Segments designed to "hook" viewers at the beginning
- YouTube-only feature (automatically enabled when specified)

## File Organization

- **Single script architecture**: All functionality in `yt-dlp-wrapper.py`
- **No build system**: Direct Python execution
- **No configuration files**: All settings are constants in the script
- **Minimal dependencies**: Only standard library + yt-dlp

## Development Considerations

- The script is designed for direct execution, not as a package
- No unit tests - rely on manual testing with real URLs
- Logging uses Python's standard logging module (INFO level default, DEBUG with --verbose)
- File operations use pathlib for cross-platform compatibility
- Browser cookie extraction validation for macOS, Linux paths
- Recursive download methods handle client fallbacks safely