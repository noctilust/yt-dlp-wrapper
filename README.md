# yt-dlp-wrapper

A single-file Python wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube, X/Twitter, and other supported sites. It adds sane defaults: resolution/codec-aware format selection, subtitles, embedded metadata, browser cookies, YouTube client fallbacks, and PO Token detection.

## Features

- **Formats**: 2160p → 1440p → 1080p → 720p, preferring av01 > vp9 > avc1.
- **YouTube Premium**: picks the highest-resolution Premium format with the best audio.
- **Subtitles and metadata**: English auto-subtitles converted to SRT; metadata embedded; chapters optional.
- **Cookies**: Chrome/Firefox/Safari fallback, skipped safely when no cookie database is readable.
- **YouTube resilience**: JS runtime detection, EJS GitHub fallback, client retries, PO Token provider detection (reports what the `yt-dlp` on PATH loaded), SABR error handling.
- **Output**: `~/Downloads/YYYY.MM.DD - <title>/` with sanitized folder names.
- **Pass-through**: unrecognized flags are forwarded to yt-dlp.

## Requirements

- Python 3.11+ (yt-dlp 2026.10.26 dropped Python 3.10).
- yt-dlp 2025.11.12+; **2026.10.26+ recommended**.
- ffmpeg for subtitle conversion and A/V merging.
- One JavaScript runtime for full YouTube support: **Deno 2.3+** (default), Node 22+, QuickJS 2023-12-9+, or Bun 1.2.11–1.3.14 (deprecated).
- A browser for cookie extraction: Chrome, Firefox, or Safari (optional; downloads work without cookies).
- Optional: `bgutil-ytdlp-pot-provider` for PO Tokens — install it in the same environment as the `yt-dlp` you run (see [PO Tokens](#po-tokens)).

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
docker run --name bgutil-provider -d -p 127.0.0.1:4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

The wrapper asks the `yt-dlp` on PATH which PO Token providers it loaded, so the plugin must be installed into that same environment (activate the venv, or run via `uv run`). Plugin and HTTP-server versions must match; see [PO Tokens](#po-tokens).

If `python3` is older than 3.11, the script searches PATH for Python 3.14–3.11 and relaunches.

## Usage

```sh
python3 yt-dlp-wrapper.py "https://www.youtube.com/watch?v=VIDEO_ID"
python3 yt-dlp-wrapper.py "https://x.com/user/status/TWEET_ID"
python3 yt-dlp-wrapper.py "URL" --format "best[height<=1080]" --verbose
```

Unknown options are forwarded to yt-dlp (`--limit-rate 1M`, `--proxy`, etc.). Extraction options apply to both metadata and download; output options apply to the download.

Run the wrapper from the environment that provides `yt-dlp` (`source .venv/bin/activate`, or `uv run ./yt-dlp-wrapper.py …`); a bare `./yt-dlp-wrapper.py` resolves whichever `yt-dlp` is first on PATH and may miss that environment's PO Token plugin.

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
2. Detect platform; check the YouTube JS runtime, then probe the `yt-dlp` on PATH for PO Token providers and check the provider's HTTP server.
3. Fetch metadata (`-j`, 5-minute timeout) and choose a Premium format if present.
4. Create the output folder and download with a 1-hour timeout.
5. On failure with no client selected, or on SABR/PO Token errors, retry YouTube clients:
   `web_embedded → tv_samsung → tv_downgraded → web_creator → web → mweb → web_safari → web_music → tv → visionos → android → ios → tv_simply`.

Downloads request English auto-subtitles, embed metadata, and use `--no-mtime`. `android_vr` is manual-only; `android_music` was removed upstream.

## PO Tokens

YouTube requires PO Tokens for some clients and formats. `bgutil-ytdlp-pot-provider` supplies them from a local HTTP server (default `http://127.0.0.1:4416`) or from a generation script.

```sh
uv pip install bgutil-ytdlp-pot-provider     # same environment as yt-dlp
docker run --name bgutil-provider -d -p 127.0.0.1:4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

Bind the published port to loopback. Upstream warns that mapping it without `127.0.0.1` exposes an unauthenticated token-generation server to your network.

Keep the plugin and the HTTP server on the same version: the plugin refuses requests when its major version differs from the server's ("Update both the plugin and the HTTP server to the same version to proceed"), so upgrade with `uv pip install -U bgutil-ytdlp-pot-provider` whenever you change the container image.

### Where the plugin must live

The plugin is a yt-dlp plugin (packaged as `yt_dlp_plugins/extractor/getpot_bgutil*`) loaded by the `yt-dlp` executable — not by the wrapper. Probing the wrapper's own imports proves nothing, and a plugin installed in a virtualenv that is not active is invisible to the `yt-dlp` on PATH.

- Preferred: install it into the environment that provides `yt-dlp` (`uv pip install` / `python3 -m pip install`), then run the wrapper from that environment. With pipx: `pipx inject yt-dlp bgutil-ytdlp-pot-provider`.
- Otherwise use a yt-dlp [plugin folder](https://github.com/yt-dlp/yt-dlp#installing-plugins): drop the release zip into `~/.config/yt-dlp/plugins/` (or `~/.yt-dlp/plugins/`), unpack it as `<name>/yt_dlp_plugins/…`, or point `--plugin-dirs DIR` at a directory holding plugin packages (`DIR/bgutil/yt_dlp_plugins/…`).

### What the wrapper checks

It runs `yt-dlp -v --simulate` against a bogus video ID, parses the `[pot] PO Token Providers:` line, and caches the result (the same list upstream verifies with `yt-dlp -v YOUTUBE_URL`):

- `✓ PO Token provider detected and ready (bgutil:http-2.0.2 (external), …)` — plus a TCP check of the server port.
- A tip naming the resolved `yt-dlp` path when no `bgutil` provider was loaded.
- Nothing when the probe is inconclusive.

`--verbose` logs the raw provider line. `--pot-provider-mode script` uses the generation script instead of the server and skips the port check; `--pot-provider-url` and `--pot-provider-script` forward custom locations. Version mismatches and other provider errors surface in yt-dlp's own output.

## Cookies and YouTube

If no browser cookie database is readable (missing profile, or macOS blocking `~/Library/Application Support`), the wrapper warns and continues without cookies; public videos still work. For authenticated content on macOS, grant Full Disk Access to your terminal or pass `--cookies cookies.txt`.

For PO Token/SABR issues, see [PO Tokens](#po-tokens), or try `--youtube-client mweb`. `--include-duplicate-formats` only exposes duplicate formats; it does not add SABR downloads.

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
