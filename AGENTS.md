# AGENTS.md — yt-dlp-wrapper

## Project structure

Single Python script (`yt-dlp-wrapper.py`), with unittest coverage in `test_yt_dlp_wrapper.py`; no build system or package config.

## Essential commands

```sh
# run the downloader
python yt-dlp-wrapper.py <URL> [options]

# update yt-dlp (the only runtime dependency managed via uv)
uv pip install -U 'yt-dlp[default]'

# optional PO Token provider (recommended for YouTube)
uv pip install bgutil-ytdlp-pot-provider
docker run --name bgutil-provider -d -p 4416:4416 --init brainicism/bgutil-ytdlp-pot-provider
```

Tests exist (test_yt_dlp_wrapper.py, run with `python3 -m unittest test_yt_dlp_wrapper`); no lint/typecheck/format commands — manual verification only.

## CLI quirks

- Uses `argparse.parse_known_args()`: unrecognized flags pass through to yt-dlp automatically.
- Default browser is `chrome` (hard-coded in `__init__` and `add_argument`). README.md was previously wrong on this; now corrected.
- `--embed-metadata` is **always** on; `--embed-chapters` is opt-in only.
- `--sponsorblock-mark`/`--sponsorblock-remove` are YouTube-only.
- Output goes to `~/Downloads/YYYY.MM.DD - <sanitized title>/`.
- `--remote-components ejs:github` is auto-added for YouTube; pass-through overrides apply after defaults in both metadata and download commands.
- `--include-duplicate-formats` exposes duplicate URLs/protocols. `--enable-sabr` is a legacy alias; neither enables SABR downloading.
- Runtime/EJS/extractor controls and selected authentication/network/config options pass through to metadata. Download/output options stay on the download command.

## Architecture facts

- **Entrypoint**: `main()`, instantiated via `VideoDownloader` class.
- **YouTube client fallback chain**: initial upstream defaults, then web_embedded → tv_downgraded → web_creator → web → mweb → web_safari → web_music → tv → visionos → android → ios → tv_simply. `android_vr` is manual-only; `android_music` was removed.
- **Browser fallback chain**: chrome → firefox → safari.
- **Format preference**: 2160p → 1440p → 1080p → 720p, codec av01 > vp9 > avc1.
- **Timeout**: 5 min metadata, 1 hour download (hard-coded in subprocess calls).
- **PO Token provider**: auto-detected (checks plugin + HTTP server on `127.0.0.1:4416`); custom URL/mode via `--pot-provider-*` flags.
- **Shared extraction settings**: `_build_extraction_args()` provides browser cookies, EJS/runtime setup, client/duplicate-format selection, and separate provider namespaces to `get_video_info()` and `_build_command()`.

## Key constraints

- Python 3.10+ required; 3.11+ recommended by upstream.
- yt-dlp >= 2025.11.12 required; 2026.08.19+ recommended for current YouTube clients.
- Deno 2.3+ (or Node.js 22+, Bun 1.2.11-1.3.14 deprecated, QuickJS) needed for YouTube format availability. The wrapper enables EJS github remote fallback automatically.
- At least one browser (Chrome/Firefox/Safari) for cookie extraction.
- `argparse` choices for `--browser`: `chrome`, `firefox`, `safari`.
- `argparse` choices for `--youtube-client`: `default`, `web`, `android`, `tv`, `tv_downgraded`, `mweb`, `web_embedded`, `web_safari`, `web_creator`, `android_vr`, `web_music`, `visionos`, `ios`, `tv_simply`.
- JavaScript runtime priority: Deno → Node → QuickJS (`qjs`) → Bun. An installed alternative is enabled automatically unless runtime flags are passed through; yt-dlp validates runtime versions.
- `--sleep-interval` is an int; `--sleep-subtitles` is a float (accepts decimals).
