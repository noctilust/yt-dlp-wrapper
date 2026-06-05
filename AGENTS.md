# AGENTS.md — yt-dlp-wrapper

## Project structure

Single Python script (`yt-dlp-wrapper.py`), no build system, no tests, no package config.

## Essential commands

```sh
# run the downloader
python yt-dlp-wrapper.py <URL> [options]

# update yt-dlp (the only runtime dependency managed via uv)
uv pip install -U yt-dlp

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
- `--remote-components ejs:github` is auto-added for YouTube (not exposed as wrapper CLI flag); pass-through of `--no-remote-components` or `ejs:npm` via extra args is supported and appended after the internal one.

## Architecture facts

- **Entrypoint**: `main()` at line 616, instantiated via `VideoDownloader` class.
- **YouTube client fallback chain**: web → android → tv → tv_downgraded → mweb → web_embedded → web_safari → web_creator → android_vr → web_music → android_music.
- **Browser fallback chain**: chrome → firefox → safari.
- **Format preference**: 2160p → 1440p → 1080p → 720p, codec av01 > vp9 > avc1.
- **Timeout**: 5 min metadata, 1 hour download (hard-coded in subprocess calls).
- **PO Token provider**: auto-detected (checks plugin + HTTP server on `127.0.0.1:4416`); custom URL/mode via `--pot-provider-*` flags.
- **EJS remote components**: `YOUTUBE_REMOTE_COMPONENT_ARGS = ['--remote-components', 'ejs:github']` is automatically injected for YouTube in `get_video_info()` (line ~292) and `_build_command()` (line ~453) so full formats and solvers are available without the yt-dlp-ejs package.

## Key constraints

- Python 3.10+ required.
- yt-dlp >= 2025.11.12 required (JavaScript runtime dependency for YouTube).
- Deno 2.3+ (or Node.js 22+, Bun 1.2.11-1.3.14 deprecated, QuickJS) needed for YouTube format availability. The wrapper enables EJS github remote fallback automatically.
- At least one browser (Chrome/Firefox/Safari) for cookie extraction.
- `argparse` choices for `--browser`: `chrome`, `firefox`, `safari`.
- `argparse` choices for `--youtube-client`: `web`, `android`, `tv`, `tv_downgraded`, `mweb`, `web_embedded`, `web_safari`, `web_creator`, `android_vr`, `web_music`, `android_music`.
- `--sleep-interval` is an int; `--sleep-subtitles` is a float (accepts decimals).
