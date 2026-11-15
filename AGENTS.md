# AGENTS.md — yt-dlp-wrapper

Agent/contributor guidance. User-facing documentation (features, options, examples) is in `README.md`.

## Project structure

Single Python script (`yt-dlp-wrapper.py`); no build system, package config, or wrapper config files. Dependencies: Python standard library + the `yt-dlp` CLI.

## Essential commands

```sh
# run the downloader
python yt-dlp-wrapper.py <URL> [options]

# update yt-dlp (the only runtime dependency managed via uv)
uv pip install -U 'yt-dlp[default]'

# optional PO Token provider (recommended for YouTube)
uv pip install bgutil-ytdlp-pot-provider
docker run --name bgutil-provider -d -p 127.0.0.1:4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

No automated tests, lint/typecheck, or format commands — manual verification only.

## Code map

- `VideoDownloader` — all behavior; `DownloadOptions` — per-download knobs; `YtDlpWrapperError` — wrapper failures.
- `DEFAULT_FORMAT_SELECTOR` — default format expression (see Format preference).
- `YOUTUBE_CLIENTS` / `YOUTUBE_FALLBACK_CLIENTS` — argparse choices / retry order.
- `SUPPORTED_PLATFORMS` — youtube.com, youtu.be, twitter.com, x.com; everything else is `other`.
- `BROWSER_FALLBACK_ORDER`, `BROWSER_PATHS`, `COOKIE_DB_GLOBS` — cookie-source selection.
- `RECOMMENDED_YTDLP_VERSION = '2026.10.26'` — startup warning threshold.
- `MIN_PYTHON_VERSION = (3, 11)` — Python floor for the bootstrap relaunch and dependency validation.
- `_build_extraction_args()` — args shared by the metadata and download commands.
- `get_video_info()` — `yt-dlp --simulate --ignore-no-formats-error -j`, 5-minute timeout.
- `download_video()` → `_run_download()` — `_run_download` is the only method that spawns the download; recursive client fallback re-enters `_run_download` (never `download_video`).

## CLI quirks

- Uses `argparse.parse_known_args()`: unrecognized flags pass through to yt-dlp automatically.
- Default browser is `chrome` (hard-coded in `__init__` and `add_argument`).
- `--embed-metadata` is **always** on; `--embed-chapters` is opt-in only.
- `--sponsorblock-mark`/`--sponsorblock-remove` are YouTube-only; categories are yt-dlp's, not the wrapper's.
- Output goes to `~/Downloads/YYYY.MM.DD - <sanitized title>/`.
- `--remote-components ejs:github` is auto-added for YouTube; pass-through overrides apply after defaults in both metadata and download commands.
- `--include-duplicate-formats` (legacy alias `--enable-sabr`) exposes duplicate YouTube URLs/protocols; neither enables SABR downloading.
- `--no-fallback` disables the client fallback chain; `--no-premium` disables Premium format detection.
- `--format-sort-reset` and `--compat-options` are wrapper options appended to the download command's pass-through args (not forwarded to metadata).
- `--pot-provider-mode` is `http` (default; server expected on `127.0.0.1:4416`) or `script`; `--pot-provider-url`/`--pot-provider-script` customize it.
- `--verbose` sets the root logger to DEBUG.
- `--sleep-interval` is an int; `--sleep-subtitles` is a float (accepts decimals).
- Runtime/EJS/extractor controls and selected authentication/network/config options pass through to metadata. Download/output options stay on the download command.

## Architecture facts

- **Entrypoint**: `main()`, instantiated via `VideoDownloader` class.
- **Flow**: validate dependencies → detect platform → YouTube JS-runtime check → PO Token provider check → `get_video_info()` → Premium format detection → create output dir → `_run_download()`.
- **Premium detection** reads the `formats` list already returned by `-j` (no second `-F` call) and picks the highest-height format whose `format_note` contains "Premium".
- **YouTube client fallback chain**: initial upstream authentication-aware defaults (unauthenticated: tv_samsung → visionos → web), then web_embedded → tv_samsung → tv_downgraded → web_creator → web → mweb → web_safari → web_music → tv → visionos → android → ios → tv_simply. `android_vr` is manual-only; `android_music` was removed.
- **Browser fallback chain**: chrome → firefox → safari, but only for browsers whose cookie database is readable; otherwise cookie extraction is skipped with a warning.
- **Format preference**: 2160p → 1440p → 1080p → 720p, codec av01 > vp9 > avc1.
- **Timeouts**: 5 min metadata, 1 hour download (hard-coded in subprocess calls).
- **PO Token provider**: auto-detected by probing the `yt-dlp` on PATH (`-v --simulate` against a bogus video ID; the `PO Token Providers:` debug line is cached and parsed) plus a TCP check of the HTTP server on `127.0.0.1:4416`; custom URL/mode via `--pot-provider-*` flags. `_detect_pot_providers()` returns `None` when the probe is inconclusive, which skips the provider messages. With fallback enabled, failed downloads log guidance and retry the fallback clients when either no client was chosen or a SABR/PO Token error is detected.
- **Error handling**: dependency validation fails fast when yt-dlp is missing, warns for old yt-dlp/ffmpeg; `download_video()` returns bool, `main()` exits 0/1.

## Key constraints

- Python 3.11+ required (yt-dlp 2026.10.26 removed Python 3.10 support).
- yt-dlp >= 2025.11.12 required; 2026.10.26+ recommended for current YouTube clients and security fixes (the wrapper warns below 2026.10.26).
- Deno 2.3+ (or Node.js 22+, Bun 1.2.11-1.3.14 deprecated, QuickJS) needed for YouTube format availability. The wrapper enables EJS github remote fallback automatically.
- At least one browser (Chrome/Firefox/Safari) for cookie extraction. Browser selection requires a readable cookie database; when none is readable (e.g. macOS blocks `~/Library/Application Support`), the wrapper omits `--cookies-from-browser` and continues.
- `argparse` choices for `--browser`: `chrome`, `firefox`, `safari`.
- `argparse` choices for `--youtube-client`: `default`, `web`, `android`, `tv`, `tv_downgraded`, `tv_samsung`, `mweb`, `web_embedded`, `web_safari`, `web_creator`, `android_vr`, `web_music`, `visionos`, `ios`, `tv_simply`.
- JavaScript runtime priority: Deno → Node → QuickJS (`qjs`) → Bun. An installed alternative is enabled automatically unless runtime flags are passed through; yt-dlp validates runtime versions.
