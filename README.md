# yt-dlp-wrapper

A single-file Python wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube, X/Twitter, and other supported sites. It adds sane defaults: resolution/codec-aware format selection, subtitles, embedded metadata, browser cookies, YouTube client fallbacks, and PO Token detection.

## Features

- **Formats**: 2160p → 1440p → 1080p → 720p, preferring av01 > vp9 > avc1.
- **YouTube Premium**: picks the highest-resolution Premium format with the best audio.
- **Subtitles and metadata**: English auto-subtitles converted to SRT; metadata embedded; chapters optional.
- **Cookies**: Chrome/Firefox/Safari fallback, skipped safely when no cookie database is readable.
- **YouTube resilience**: JS runtime detection, EJS GitHub fallback, client retries, PO Token/SABR detection.
- **Output**: `~/Downloads/YYYY.MM.DD - <title>/` with sanitized folder names.
- **Pass-through**: unrecognized flags are forwarded to yt-dlp.

## Requirements

- Python 3.11+ (yt-dlp 2026.10.26 dropped Python 3.10).
- yt-dlp 2025.11.12+; **2026.10.26+ recommended**.
- ffmpeg for subtitle conversion and A/V merging.
- One JavaScript runtime for full YouTube support: **Deno 2.3+** (default), Node 22+, QuickJS 2023-12-9+, or Bun 1.2.11–1.3.14 (deprecated).
- A browser for cookie extraction: Chrome, Firefox, or Safari (optional; downloads work without cookies).
- Optional: `bgutil-ytdlp-pot-provider` for PO Tokens.

## Installation

```sh
git clone https://github.com/noctilust/yt-dlp-wrapper.git
cd yt-dlp-wrapper
chmod +x yt-dlp-wrapper.py

uv pip install -U 'yt-dlp[default]'   # or: pipx install 'yt-dlp[default]'
brew install deno                      # or install Node 22+, QuickJS, or Bun
```

Optional PO Token provider:

```sh
uv pip install bgutil-ytdlp-pot-provider
docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

The plugin is loaded by the `yt-dlp` executable, not by the wrapper, so it must be installed into the environment that provides `yt-dlp` on PATH (activate that venv before running). The wrapper probes the executable and reports which PO Token providers it loaded. Keep the plugin and the HTTP server on the same version (`uv pip install -U bgutil-ytdlp-pot-provider`); the plugin refuses requests when major versions differ.

If `python3` is older than 3.11, the script searches PATH for Python 3.14–3.11 and relaunches.

## Usage

```sh
python3 yt-dlp-wrapper.py "https://www.youtube.com/watch?v=VIDEO_ID"
python3 yt-dlp-wrapper.py "https://x.com/user/status/TWEET_ID"
python3 yt-dlp-wrapper.py "URL" --format "best[height<=1080]" --verbose
```

Unknown options are forwarded to yt-dlp (`--limit-rate 1M`, `--proxy`, etc.). Extraction options apply to both metadata and download; output options apply to the download.

### Options

| Option | Description |
|---|---|
| `--format, -f` | Custom yt-dlp format selector |
| `--browser, -b` | Cookie source: `chrome` (default), `firefox`, `safari` |
| `--youtube-client, -y` | Force a YouTube client (see list below) |
| `--no-fallback` | Disable YouTube client retries |
| `--no-premium` | Ignore Premium formats |
| `--include-duplicate-formats` | Include alternate URLs/protocols (legacy alias `--enable-sabr`; does not enable SABR) |
| `--sponsorblock-mark CATS` | Mark segments as chapters (YouTube only) |
| `--sponsorblock-remove CATS` | Remove segments (YouTube only) |
| `--embed-chapters` | Embed chapters |
| `--sleep-interval SEC` | Delay between downloads (int) |
| `--sleep-subtitles SEC` | Delay between subtitle downloads (float) |
| `--format-sort-reset` | Reset yt-dlp format sorting |
| `--compat-options OPTS` | yt-dlp compatibility options (e.g. `2025`) |
| `--pot-provider-mode` | `http` (default) or `script` |
| `--pot-provider-url` | Custom PO Token server URL |
| `--pot-provider-script` | Provider script path |
| `--verbose, -v` | DEBUG logging |
| `--help, -h` | Help |

`--youtube-client` choices: `default`, `web`, `android`, `tv`, `tv_downgraded`, `tv_samsung`, `mweb`, `web_embedded`, `web_safari`, `web_creator`, `android_vr`, `web_music`, `visionos`, `ios`, `tv_simply`.

## Behavior

1. Validate dependencies; select the first browser with a readable cookie database.
2. Detect platform; check the YouTube JS runtime and PO Token setup.
3. Fetch metadata (`-j`, 5-minute timeout) and choose a Premium format if present.
4. Create the output folder and download with a 1-hour timeout.
5. On failure with no client selected, or on SABR/PO Token errors, retry YouTube clients:
   `web_embedded → tv_samsung → tv_downgraded → web_creator → web → mweb → web_safari → web_music → tv → visionos → android → ios → tv_simply`.

Downloads request English auto-subtitles, embed metadata, and use `--no-mtime`. `android_vr` is manual-only; `android_music` was removed upstream.

## Cookies and YouTube

If no browser cookie database is readable (missing profile, or macOS blocking `~/Library/Application Support`), the wrapper warns and continues without cookies; public videos still work. For authenticated content on macOS, grant Full Disk Access to your terminal or pass `--cookies cookies.txt`.

For PO Token/SABR issues, install `bgutil-ytdlp-pot-provider` and run its HTTP server (above), or try `--youtube-client mweb`. `--include-duplicate-formats` only exposes duplicate formats; it does not add SABR downloads.

## SponsorBlock

YouTube only. Categories come from yt-dlp (`sponsor`, `intro`, `outro`, `selfpromo`, `filler`, `interaction`, `music_offtopic`, `hook`, `poi_highlight`, `chapter`, `all`):

```sh
python3 yt-dlp-wrapper.py "URL" --sponsorblock-mark all --embed-chapters
python3 yt-dlp-wrapper.py "URL" --sponsorblock-remove sponsor,intro
```

## Upstream compatibility

Reviewed against yt-dlp 2026.10.26 (2026-11-05), including the `tv_samsung` default client and Python 3.11 requirement. The wrapper adds `--remote-components ejs:github` for YouTube so EJS solvers can be fetched when `yt-dlp-ejs` is absent; `yt-dlp[default]` already bundles them. Timeouts are 5 minutes for metadata and 1 hour for downloads; exit codes are 0 (success) and 1 (failure).

## License

MIT License
