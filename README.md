# yt-dlp-wrapper

Vibe coding an optimized Python wrapper script for [yt-dlp](https://github.com/yt-dlp/yt-dlp) that intelligently downloads videos from various platforms including YouTube and X (Twitter). The script features robust error handling, multiple browser support, and smart format selection with codec preferences (av01 > vp9 > avc1). It organizes downloads in well-named folders and includes comprehensive logging.

## Features

- **Smart Format Selection**: Optimized format selector with resolution priority (4K > 2K > 1080p > 720p) and codec preference (av01 > vp9 > avc1)
- **Premium Format Detection**: Automatically detects and uses YouTube Premium formats when available
- **JavaScript Runtime Detection**: Checks for Deno/Node.js/QuickJS/Bun and enables an installed alternative when Deno is absent; yt-dlp validates runtime versions
- **EJS Remote Component Fallback**: Automatically passes `--remote-components ejs:github` for YouTube (in metadata and download) to fetch solver scripts from GitHub when the yt-dlp-ejs package is not installed
- **Multi-Browser Support**: Extract cookies from Firefox, Chrome, or Safari for authenticated downloads
- **Robust Error Handling**: Comprehensive validation, timeout protection, and graceful failure handling
- **Multi-Platform Support**: Works with YouTube, X (Twitter), and other platforms supported by yt-dlp
- **SponsorBlock Integration**: Mark or remove sponsor segments, intros, outros, and other video sections (YouTube only)
- **Subtitle Download**: Downloads English auto-generated subtitles (all variants: en, en-US, etc.) and converts them to SRT format with error handling
- **Organized Output**: Creates folders named `YYYY.MM.DD - <Video Title>` in your `~/Downloads` directory
- **Advanced Logging**: Configurable logging levels with detailed progress information
- **Custom Format Support**: Override default format selection with custom selectors
- **Dependency Validation**: Automatic checking of Python 3.10+, yt-dlp CLI, ffmpeg, JavaScript runtime, and browsers (with failover)
- **Timeout Protection**: 5 minutes for metadata, 1 hour for downloads
- **YouTube Client Fallbacks**: Retries alternative clients when download formats fail, including SABR restrictions
- **PO Token Provider Integration**: Automatic detection and integration with bgutil-ytdlp-pot-provider plugin for bypassing YouTube bot detection
- **PO Token Error Detection**: Detects PO Token errors and recommends plugin installation or suggests appropriate client options

## Format Selection Strategy

The script uses yt-dlp's advanced format selector with the following priority:

1. **Resolution Priority**: 4K (2160p) → 2K (1440p) → 1080p → 720p
2. **Codec Priority**: Within each resolution, prefers av01 > vp9 > avc1
3. **Fallback**: Best available format if preferred options aren't available

## Requirements

- Python 3.10+; Python 3.11+ recommended by upstream since 2026.07.04 (3.10 support will be dropped soon)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) **2025.11.12 or later** (recommended for full YouTube support)
  - **2026.08.19 or later recommended** for the current client list and YouTube fixes
  - Install/update with: `uv pip install -U 'yt-dlp[default]'` (includes matching EJS scripts)
- JavaScript runtime (required for YouTube as of yt-dlp 2025.11.12):
  - **Deno 2.3+** (recommended): `brew install deno` (macOS) or see https://deno.land/
  - Alternative runtimes: Node.js 22+, Bun 1.2.11-1.3.14 (deprecated), or QuickJS 2023-12-9+
  - QuickJS must be available as `qjs`; runtime priority is Deno → Node → QuickJS → Bun
  - Use pass-through `--no-js-runtimes --js-runtimes node:/path/to/node` to select a runtime explicitly
  - Without a runtime, YouTube downloads will have severely limited format availability
  - The wrapper allows yt-dlp to fetch EJS solver scripts from GitHub for YouTube when local EJS components are missing or stale
- At least one supported browser: Firefox, Chrome, or Safari (for cookie extraction)
- **PO Token provider plugin** (optional but recommended for YouTube):
  - Plugin: `uv pip install bgutil-ytdlp-pot-provider`
  - HTTP server: `docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider`
  - Automatically bypasses YouTube bot detection and PO Token requirements
  - See https://github.com/Brainicism/bgutil-ytdlp-pot-provider for more details

## Installation

1. Clone this repository or copy `yt-dlp-wrapper.py` to your local machine.
2. Install yt-dlp CLI tool (2026.08.19 or later recommended):
    ```sh
    # Using uv (recommended)
    uv pip install -U 'yt-dlp[default]'

    # Or using pipx (isolated installation)
    pipx install 'yt-dlp[default]'

    # Verify installation (2026.08.19 or later recommended)
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

    # Or use Node.js setup (yt-dlp EJS requires Node.js 22+)
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

**Include duplicate YouTube formats (alternative URLs/protocols):**
```sh
python yt-dlp-wrapper.py "URL" --include-duplicate-formats
```

The legacy `--enable-sabr` alias has the same effect. Neither flag enables SABR downloading.

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
- `--browser, -b`: Browser to extract cookies from (default: chrome; options: firefox, chrome, safari)
- `--verbose, -v`: Enable detailed logging output
- `--youtube-client, -y`: YouTube client to use (default, web, android, tv, tv_downgraded, mweb, web_embedded, web_safari, web_creator, android_vr, web_music, visionos, ios, tv_simply)
- `--include-duplicate-formats`: Include duplicate YouTube format URLs/protocols
- `--enable-sabr`: Legacy alias for `--include-duplicate-formats`; does not enable SABR downloading
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

Metadata extraction also receives the selected YouTube client, duplicate-format setting, custom PO Token provider settings, and pass-through runtime/EJS/extractor controls. Browser cookie overrides, proxy/impersonation settings, source address, socket timeout, config/plugin locations, IP version, and `--no-playlist` also apply to the metadata request. Download/output options stay on the download command. Pass-through controls such as `--no-remote-components` take precedence over wrapper defaults in both stages.

## What the script does

### On Startup (in `__init__`)
1. **Validates dependencies** - Checks for Python 3.10+, yt-dlp CLI tool, ffmpeg availability, and supported browser availability

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
   - Remote EJS component fallback (`--remote-components ejs:github`, YouTube only)
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

- **Browser Support**: Defaults to Chrome; checks browser paths and falls back through Chrome → Firefox → Safari when the preferred browser is unavailable.
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
- **YouTube Client Fallback**: Leaves the first attempt on upstream defaults, then retries web_embedded → tv_downgraded → web_creator → web → mweb → web_safari → web_music → tv → visionos → android → ios → tv_simply (unless `--no-fallback` is used). `android_vr` is manual-only because upstream reports 403 errors for its formats; `android_music` is no longer supported.
- **JavaScript Runtime**: Warns if no runtime executable is detected; enables an installed alternative unless the user passes runtime controls. yt-dlp checks supported versions.

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

1. **Automatic Client Fallback**: Leaves client selection to yt-dlp on the initial attempt, including its authentication-aware defaults. Retries prefer cookie-capable clients and retain custom extractor/provider settings. See the fallback order above.

2. **Manual Client Selection**: You can manually specify which YouTube client to use with `--youtube-client`. Available clients:
   - `default` - Let yt-dlp choose clients for the current session
   - `web`, `web_safari` - Web clients (SABR restrictions can limit formats)
   - `web_embedded` - Embedded web client; used by upstream for logged-in free accounts
   - `web_creator` - Requires authentication; used by upstream for Premium accounts
   - `android`, `ios`, `tv_simply` - Alternative clients; cookie authentication is unsupported
   - `visionos` - Added in 2026.08.19; part of upstream's defaults without login, does not support cookie authentication
   - `tv`, `tv_downgraded` - TV clients supporting cookie authentication
   - `mweb` - Mobile web client (alternative for PO Token issues)
   - `web_music` - YouTube Music web client
   - `android_vr` - Manual-only; upstream reports 403 errors for its formats

3. **PO Token Error Detection**: The wrapper automatically detects PO Token errors and recommends installing the plugin or trying the `mweb` client.

4. **Duplicate Formats**: `--include-duplicate-formats` (legacy alias `--enable-sabr`) sets `youtube:formats=duplicate`. This exposes alternate URLs/protocols for identical content. Upstream still skips SABR formats without a downloadable URL; this option does not add SABR support.

5. **Error Detection**: The wrapper automatically detects SABR-related errors and provides appropriate fallback solutions.

6. **Fallback Limiting**: Prevents infinite recursion by disabling fallbacks during retry attempts.

### Upstream compatibility review (2026-10-04)

Reviewed [stable 2026.08.19](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.08.19) and master through [51bab8a011](https://github.com/yt-dlp/yt-dlp/commit/51bab8a011) (2026-09-27). The wrapper now matches the [current client list](https://github.com/yt-dlp/yt-dlp/blob/51bab8a011/README.md#youtube), uses separate extractor namespaces for providers, and follows [EJS runtime setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS). The existing GitHub EJS fallback remains supported. Python 3.10 still works; upstream recommends 3.11+. September's `web_embedded` user-agent fix is internal to yt-dlp and requires no wrapper change.

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
