# yt-dlp-wrapper

Vibe coding an optimized Python wrapper script for [yt-dlp](https://github.com/yt-dlp/yt-dlp) that intelligently downloads videos from various platforms including YouTube and X (Twitter). The script features robust error handling, multiple browser support, and smart format selection with codec preferences (av01 > vp9 > avc1). It organizes downloads in well-named folders and includes comprehensive logging.

## Features

- **Smart Format Selection**: Optimized format selector with resolution priority (4K > 2K > 1080p > 720p) and codec preference (av01 > vp9 > avc1)
- **Premium Format Detection**: Automatically detects and uses YouTube Premium formats when available
- **JavaScript Runtime Validation**: Checks for Deno/Node.js/Bun/QuickJS for YouTube downloads (required as of yt-dlp 2025.11.12)
- **Multi-Browser Support**: Extract cookies from Firefox, Chrome, or Safari for authenticated downloads
- **Robust Error Handling**: Comprehensive validation, timeout protection, and graceful failure handling
- **Multi-Platform Support**: Works with YouTube, X (Twitter), and other platforms supported by yt-dlp
- **SponsorBlock Integration**: Mark or remove sponsor segments, intros, outros, and other video sections (YouTube only)
- **Subtitle Download**: Downloads English auto-generated subtitles (all variants: en, en-US, etc.) and converts them to SRT format with error handling
- **Organized Output**: Creates folders named `YYYY.MM.DD - <Video Title>` in your `~/Downloads` directory
- **Advanced Logging**: Configurable logging levels with detailed progress information
- **Custom Format Support**: Override default format selection with custom selectors
- **Dependency Validation**: Automatic checking of Python 3.10+, yt-dlp CLI, JavaScript runtime, and browsers
- **Timeout Protection**: 5 minutes for metadata, 1 hour for downloads
- **YouTube SABR Support**: Handles YouTube's Server-side Adaptive Bitrate streaming protocol with automatic client fallbacks
- **PO Token Provider Integration**: Automatic detection and integration with bgutil-ytdlp-pot-provider plugin for bypassing YouTube bot detection
- **PO Token Error Detection**: Detects PO Token errors and recommends plugin installation or suggests appropriate client options

## Format Selection Strategy

The script uses yt-dlp's advanced format selector with the following priority:

1. **Resolution Priority**: 4K (2160p) → 2K (1440p) → 1080p → 720p
2. **Codec Priority**: Within each resolution, prefers av01 > vp9 > avc1
3. **Fallback**: Best available format if preferred options aren't available

## Requirements

- Python 3.10+ (enforced as of yt-dlp 2025.10.22)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) **2025.11.12 or later** (recommended for full YouTube support)
  - Earlier versions may work but will have limited YouTube format availability
  - Install/update with: `uv pip install -U yt-dlp`
- JavaScript runtime (required for YouTube as of yt-dlp 2025.11.12):
  - **Deno** (recommended): `brew install deno` (macOS) or see https://deno.land/
  - Alternative runtimes: Node.js 20+, Bun 1.0.31+, or QuickJS 2023-12-9+
  - Without a runtime, YouTube downloads will have severely limited format availability
- At least one supported browser: Firefox, Chrome, or Safari (for cookie extraction)
- **PO Token provider plugin** (optional but recommended for YouTube):
  - Plugin: `uv pip install bgutil-ytdlp-pot-provider`
  - HTTP server: `docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider`
  - Automatically bypasses YouTube bot detection and PO Token requirements
  - See https://github.com/Brainicism/bgutil-ytdlp-pot-provider for more details

## Installation

1. Clone this repository or copy `yt-dlp-wrapper.py` to your local machine.
2. Install yt-dlp CLI tool (version 2025.11.12 or later):
    ```sh
    # Using uv (recommended)
    uv pip install -U yt-dlp

    # Or using pipx (isolated installation)
    pipx install yt-dlp

    # Verify installation (should show 2025.11.12 or later)
    yt-dlp --version
    ```
3. Install a JavaScript runtime (required for YouTube):
    ```sh
    # macOS (using Homebrew)
    brew install deno

    # Linux
    curl -fsSL https://deno.land/install.sh | sh

    # Windows (PowerShell)
    irm https://deno.land/install.ps1 | iex
    ```
4. (Optional but recommended) Install PO Token provider plugin for enhanced YouTube support:
    ```sh
    # Install the plugin
    uv pip install bgutil-ytdlp-pot-provider

    # Start the HTTP server with Docker
    docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider

    # Or use Node.js setup (requires Node.js 18+)
    # See https://github.com/Brainicism/bgutil-ytdlp-pot-provider
    ```
5. (Optional) Make the script executable:
    ```sh
    chmod +x yt-dlp-wrapper.py
    ```

## Usage

### Basic Usage

Run the script with a video URL from a supported platform:

**YouTube:**
```sh
python yt-dlp-wrapper.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

**X (Twitter):**
```sh
python yt-dlp-wrapper.py "https://twitter.com/username/status/YOUR_TWEET_ID"
```

**Other platforms:**
```sh
python yt-dlp-wrapper.py "https://example.com/video"
```

### Advanced Options

**Custom format selection:**
```sh
python yt-dlp-wrapper.py "URL" --format "best[height<=720]"
```

**Use different browser for cookies:**
```sh
python yt-dlp-wrapper.py "URL" --browser chrome
python yt-dlp-wrapper.py "URL" --browser safari
```

**Enable verbose logging:**
```sh
python yt-dlp-wrapper.py "URL" --verbose
```

**Combine options:**
```sh
python yt-dlp-wrapper.py "URL" --browser chrome --format "best[height<=1080]" --verbose
```

**Handle YouTube SABR streaming issues:**
```sh
python yt-dlp-wrapper.py "URL" --youtube-client android
```

**Enable SABR format support:**
```sh
python yt-dlp-wrapper.py "URL" --enable-sabr
```

**Disable Premium format detection:**
```sh
python yt-dlp-wrapper.py "URL" --no-premium
```

**Use SponsorBlock to mark or remove segments:**
```sh
python yt-dlp-wrapper.py "URL" --sponsorblock-mark all --embed-chapters
python yt-dlp-wrapper.py "URL" --sponsorblock-remove sponsor
```

**Add rate limiting for batch downloads:**
```sh
python yt-dlp-wrapper.py "URL" --sleep-interval 5
```

**Use PO Token provider in script mode (no server needed):**
```sh
python yt-dlp-wrapper.py "URL" --pot-provider-mode script
```

**Use custom PO Token provider server:**
```sh
python yt-dlp-wrapper.py "URL" --pot-provider-url "http://localhost:8080"
```

### Command-Line Options

- `--format, -f`: Custom format selector (overrides default smart selection)
- `--browser, -b`: Browser to extract cookies from (default: firefox; options: firefox, chrome, safari)
- `--verbose, -v`: Enable detailed logging output
- `--youtube-client, -y`: YouTube client to use (web, android, tv, tv_downgraded, mweb, web_music, android_music)
- `--enable-sabr`: Enable YouTube SABR streaming format support
- `--no-fallback`: Disable automatic fallback to other YouTube clients
- `--no-premium`: Disable automatic selection of Premium formats
- `--sponsorblock-mark CATS`: Mark SponsorBlock categories as chapters (e.g., "all", "sponsor,intro,outro,hook")
- `--sponsorblock-remove CATS`: Remove SponsorBlock categories from video (e.g., "sponsor")
- `--embed-chapters`: Embed chapter markers in video file
- `--sleep-interval SECONDS`: Sleep interval between downloads (recommended: 5-10 seconds)
- `--pot-provider-mode MODE`: PO Token provider mode (http or script)
- `--pot-provider-url URL`: Custom PO Token provider HTTP server URL (default: http://127.0.0.1:4416)
- `--pot-provider-script PATH`: Path to PO Token provider script (for script mode)
- `--help, -h`: Show help message with examples

### Pass-through Arguments

The wrapper uses `argparse.parse_known_args()` to forward any unrecognized arguments directly to the yt-dlp CLI. This allows you to use any standard yt-dlp option alongside the wrapper's custom options:

```sh
python yt-dlp-wrapper.py "URL" --verbose --limit-rate 1M --no-playlist
```

## What the script does

### On Startup (in `__init__`)
1. **Validates dependencies** - Checks for Python 3.10+, yt-dlp CLI tool, and Firefox browser availability (if selected)

### During Download
2. **Detects platform** from the URL (YouTube, X/Twitter, or other)
3. **Validates YouTube requirements** - Checks for JavaScript runtime (Deno/Node.js/Bun/QuickJS) and warns if missing
4. **Validates PO Token provider** - Checks if bgutil-ytdlp-pot-provider plugin is installed and HTTP server is running (for YouTube)
5. **Checks for Premium formats** - For YouTube videos, automatically detects and selects YouTube Premium formats when available (unless `--no-premium` is used)
6. **Fetches video metadata** - Retrieves title, upload date, and other information with 5-minute timeout protection
7. **Creates output directory** - Generates organized folder structure (`YYYY.MM.DD - Video Title`) with sanitized names (max 100 characters)
8. **Builds yt-dlp command** - Constructs command with:
   - Cookie extraction from specified browser
   - Format selector (Premium or default)
   - Subtitle download flags (`--write-auto-sub --sub-lang en.* --convert-subs srt`)
   - Metadata embedding (`--embed-metadata` always included)
   - Chapter embedding (`--embed-chapters` only if flag specified)
   - SponsorBlock options (YouTube only, if specified)
   - YouTube client selection (if specified)
   - PO Token provider configuration (if custom settings provided)
   - Rate limiting (if `--sleep-interval` specified)
9. **Executes download** - Runs yt-dlp command with 1-hour timeout protection
10. **Handles errors automatically** - Detects SABR/PO Token errors, provides plugin installation guidance, and tries fallback YouTube clients if enabled

## Example

```sh
python yt-dlp-wrapper.py "https://www.youtube.com/watch?v=u2Ftw_VuedA"
```

This will:
1. Check for JavaScript runtime (Deno/Node.js/etc.) and warn if missing
2. Check for Premium formats and use them if available
3. Fetch video metadata to get title and upload date
4. Create output directory: `~/Downloads/YYYY.MM.DD - Video Title/`
5. Download the highest quality available using format priority:
   - Resolution: 4K (2160p) → 2K (1440p) → 1080p → 720p
   - Codec (within each resolution): av01 > vp9 > avc1
6. Download English auto-generated subtitles (all variants) and convert to SRT
7. Embed metadata in the video file
8. Automatically handle SABR/PO Token errors with client fallbacks if needed

## Notes

- **Browser Support**: Defaults to Firefox but supports Chrome and Safari via `--browser` option. Only Firefox has path validation; Chrome/Safari are passed directly to yt-dlp.
- **Error Handling**: Script validates dependencies on startup and provides clear error messages
- **Timeout Protection**: 5 minutes for metadata extraction, 1 hour for downloads
- **Output Organization**: Folder names are sanitized and limited to 100 characters for filesystem compatibility
- **Logging**: Uses proper logging levels (INFO by default, DEBUG with `--verbose`)
- **Exit Codes**: Returns proper exit codes (0 for success, 1 for failure) for scripting
- **Metadata Embedding**: Automatically embeds video metadata in all downloaded files (via `--embed-metadata`)
- **Chapter Embedding**: Chapters are only embedded when `--embed-chapters` flag is explicitly used
- **File Timestamps**: Uses `--no-mtime` to prevent setting file modification time to video upload date
- **Format Selection**: Uses optimized regex-based format selector for better performance
- **Graceful Degradation**: Continues working even if browser cookies aren't available
- **YouTube Client Fallback**: Automatically tries alternative YouTube clients (android, tv, tv_downgraded, mweb, web_music, android_music) if the default fails (unless `--no-fallback` is used)
- **JavaScript Runtime**: Warns if no JavaScript runtime is detected for YouTube downloads (but continues with limited format availability)

## YouTube SABR Streaming & PO Token Handling

Starting in 2025, YouTube began rolling out a new streaming protocol called SABR (Server-side Adaptive Bitrate) and PO Token requirements, which have impacted tools like yt-dlp. When YouTube serves content via SABR or requires a PO Token, traditional download methods may fail or only retrieve lower quality formats.

This wrapper includes comprehensive features to handle SABR streaming and PO Token errors:

### PO Token Provider Integration (Recommended Solution)

The wrapper automatically integrates with the **bgutil-ytdlp-pot-provider** plugin, which provides automated PO Token generation:

1. **Automatic Detection**: The wrapper checks if the plugin is installed and the HTTP server is running
2. **Helpful Guidance**: If not detected, provides clear installation instructions with Docker command
3. **Custom Configuration**: Supports custom server URLs and script mode via command-line options:
   - `--pot-provider-mode script` - Use script mode (slower but no server needed)
   - `--pot-provider-url URL` - Custom HTTP server URL
   - `--pot-provider-script PATH` - Custom script path

**Installation:**
```sh
# Install the plugin
uv pip install bgutil-ytdlp-pot-provider

# Start the HTTP server with Docker (recommended)
docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

### Alternative Solutions

1. **Automatic Client Fallback**: If a download fails due to SABR restrictions or PO Token errors, the wrapper will automatically try alternative YouTube clients: `android`, `tv`, `tv_downgraded`, `mweb`, `web_music`, `android_music`.

2. **Manual Client Selection**: You can manually specify which YouTube client to use with `--youtube-client`. Available clients:
   - `web` - Default web client (may use SABR streaming)
   - `android` - Android client (often still provides traditional formats)
   - `tv` - TV client (often still provides traditional formats)
   - `tv_downgraded` - TV client with downgraded version (prevents SABR on logged-in accounts)
   - `mweb` - Mobile web client (alternative for PO Token issues)
   - `web_music` - YouTube Music web client
   - `android_music` - YouTube Music android client

3. **PO Token Error Detection**: The wrapper automatically detects PO Token errors and recommends installing the plugin or trying the `mweb` client.

4. **SABR Format Support**: If needed, you can enable SABR format support with `--enable-sabr`. This requires yt-dlp 2025.11.12 or later with SABR streaming support.

5. **Error Detection**: The wrapper automatically detects SABR-related errors and provides appropriate fallback solutions.

6. **Fallback Limiting**: Prevents infinite recursion by disabling fallbacks during retry attempts.

## YouTube Premium Formats

The wrapper automatically detects and prioritizes YouTube Premium formats when available. Premium formats (such as format ID 616) often provide better quality video with enhanced bitrates.

Key features of the Premium format detection:

1. **Automatic Detection**: The wrapper scans the available formats and automatically selects Premium formats when detected.

2. **Smart Premium Quality**: When multiple Premium formats are available, automatically selects the one with the highest resolution.

3. **Manual Control**: You can disable Premium format selection with `--no-premium` if you prefer to use the default format selector.

4. **Best Audio Pairing**: When using Premium video formats, the wrapper automatically selects the best available audio to pair with it.

This feature is particularly useful for high-quality archiving of YouTube content that includes Premium format options.

## SponsorBlock Integration

The wrapper includes built-in SponsorBlock support for YouTube videos, allowing you to automatically mark or remove sponsored segments and other video sections.

### Features

- **Mark Segments as Chapters**: Use `--sponsorblock-mark CATEGORIES` to mark SponsorBlock segments as chapters in the video file
- **Remove Segments**: Use `--sponsorblock-remove CATEGORIES` to completely remove unwanted segments from the downloaded video
- **YouTube Only**: SponsorBlock features are automatically enabled only for YouTube videos

### Available Categories

- `sponsor` - Paid promotions and sponsorships
- `intro` - Intro sequences
- `outro` - Outro sequences and endcards
- `selfpromo` - Self-promotion (merch, donations, etc.)
- `preview` - Preview or recap of other videos
- `filler` - Filler tangent or off-topic content
- `interaction` - Reminder to like, subscribe, or follow
- `music_offtopic` - Non-music sections in music videos
- `hook` - Segments designed to "hook" viewers at the beginning (added in yt-dlp 2025.11.12)
- `poi_highlight` - Points of interest highlights
- `chapter` - Chapter markers
- `all` - All categories

### Examples

**Mark all SponsorBlock categories as chapters:**
```sh
python yt-dlp-wrapper.py "URL" --sponsorblock-mark all --embed-chapters
```

**Remove only sponsor segments:**
```sh
python yt-dlp-wrapper.py "URL" --sponsorblock-remove sponsor
```

**Mark sponsors and intros, remove outros:**
```sh
python yt-dlp-wrapper.py "URL" --sponsorblock-mark "sponsor,intro" --sponsorblock-remove outro --embed-chapters
```

## License

MIT License

---