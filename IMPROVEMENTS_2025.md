# yt-dlp-wrapper Improvements - 2025-2026

## Summary

This document summarizes all improvements made to the yt-dlp-wrapper based on the latest yt-dlp changes (as of 2025.11.12) and best practices research.

## 2026.05.08 — Maintenance Updates

### 1. ffmpeg Validation
- **Issue**: ffmpeg required for subtitle conversion (SRT) and video/audio merging, but missing silently
- **Solution**: Added `shutil.which('ffmpeg')` check in `_validate_dependencies()` with user-friendly warning
- **Impact**: Users now know upfront if ffmpeg is missing, rather than cryptic yt-dlp failures mid-download
- **Code**: Warning message with `brew install ffmpeg` remediation

### 2. yt-dlp Version Check
- **Issue**: Wrapper validated `yt-dlp` was in PATH but never checked version; old versions could cause unexpected behavior
- **Solution**: Added version parse check using `packaging.version.Version`, warns if below `2025.11.12`
- **Impact**: Users with outdated yt-dlp get actionable upgrade guidance
- **Code**: `subprocess.run(['yt-dlp', '--version'])` with `packaging.version.Version` comparison

### 3. `_validate_pot_provider` Return Type Cleaned Up
- **Issue**: Method signature declared `-> Optional[str]` but always returned `None`; return value was discarded at call site
- **Solution**: Changed to `-> None`, removed all redundant `return None` statements; docstring updated to clarify it logs and doesn't return
- **Impact**: No functional change — cleaner type signature, avoids misleading return value
- **Code**: Changed signature and pruned dead returns

---

## Critical Updates (Must Do) ✅

### 1. JavaScript Runtime Validation for YouTube
- **Issue**: As of yt-dlp 2025.11.12, an external JavaScript runtime is required for full YouTube support
- **Solution**: Added automatic detection for Deno, Node.js, Bun, and QuickJS
- **Impact**: Users are warned if no runtime is detected, with helpful installation instructions
- **Code**: `_check_javascript_runtime()` and `_validate_youtube_requirements()` methods

### 2. Python 3.10+ Version Check
- **Issue**: yt-dlp raised minimum Python version to 3.10 as of 2025.10.22
- **Solution**: Added version validation in `_validate_dependencies()`
- **Impact**: Prevents runtime failures with clear error message

### 3. New YouTube Clients
- **Issue**: yt-dlp added new clients for better compatibility
- **Solution**: Added `tv_downgraded` and `mweb` to `YOUTUBE_CLIENTS` list
  - `tv_downgraded`: Prevents SABR format issues on logged-in accounts
  - `mweb`: Recommended for PO Token-related errors
- **Impact**: Better download success rate for problematic videos

## Feature Additions (Should Do) ✅

### 4. SponsorBlock Integration
- **Feature**: Native SponsorBlock support for YouTube videos
- **Options Added**:
  - `--sponsorblock-mark CATS`: Mark categories as chapters (sponsor, intro, outro, etc.)
  - `--sponsorblock-remove CATS`: Remove unwanted segments from video
- **Impact**: Users can automatically skip/remove sponsors, intros, outros
- **Example**: `--sponsorblock-mark all --embed-chapters`

### 5. Chapter Embedding
- **Feature**: Separated chapter embedding from metadata for granular control
- **Option Added**: `--embed-chapters`
- **Impact**: Better control over metadata vs. chapters in video files

### 6. Rate Limiting
- **Feature**: Sleep interval between downloads to avoid YouTube rate limits
- **Option Added**: `--sleep-interval SECONDS`
- **Recommended**: 5-10 seconds between downloads
- **Impact**: Prevents hitting YouTube's rate limits (300 videos/hour guest, 2000/hour authenticated)

## Enhanced Error Handling (Nice to Have) ✅

### 7. PO Token Error Detection
- **Feature**: Intelligent detection and helpful guidance for PO Token errors
- **Solution**: Added detection for PO Token-related errors with actionable suggestions
- **Guidance Provided**:
  - Suggests using `--youtube-client mweb`
  - Links to yt-dlp wiki for advanced PO Token configuration
  - Prevents confusing error messages

### 8. Improved Warning Messages
- **Feature**: Enhanced user-friendly warnings with emojis and clear formatting
- **Examples**:
  - JavaScript runtime warnings with installation commands
  - PO Token errors with specific client recommendations
  - SABR streaming issue detection

## Documentation Updates ✅

### 9. Updated CLAUDE.md
- **Changes**:
  - Updated Python requirement to 3.10+
  - Added JavaScript runtime (Deno) as critical dependency
  - Added all new command-line options with examples
  - Updated YouTube clients list
  - Added SponsorBlock integration documentation
  - Enhanced error handling documentation
  - Updated video processing flow

## Testing Results

All features tested successfully:
- ✅ Python version check (3.14.0 detected)
- ✅ JavaScript runtime detection (Deno 2.5.6 detected)
- ✅ New clients available (tv_downgraded, mweb)
- ✅ SponsorBlock integration working
- ✅ Chapter embedding functional
- ✅ Rate limiting option available
- ✅ PO Token error detection ready
- ✅ Download success with all new features

## Key Benefits

1. **Better Compatibility**: Support for latest yt-dlp requirements and features
2. **Enhanced User Experience**: Clear warnings and helpful guidance
3. **More Control**: SponsorBlock, chapters, rate limiting options
4. **Reduced Errors**: Better error detection and fallback mechanisms
5. **Future-Proof**: Aligned with yt-dlp 2025 roadmap

## Backward Compatibility

All changes are backward compatible:
- New options are optional
- Existing command-line arguments work as before
- Default behavior unchanged (except for new validation warnings)

## Command Examples

```bash
# Basic download with new validations
python yt-dlp-wrapper.py "https://youtube.com/watch?v=VIDEO_ID"

# Use new client for problematic videos
python yt-dlp-wrapper.py "URL" --youtube-client tv_downgraded

# SponsorBlock with chapters
python yt-dlp-wrapper.py "URL" --sponsorblock-mark all --embed-chapters

# Rate limiting for batch downloads
python yt-dlp-wrapper.py "URL" --sleep-interval 5

# Handle PO Token issues
python yt-dlp-wrapper.py "URL" --youtube-client mweb

# All features combined
python yt-dlp-wrapper.py "URL" \
  --youtube-client tv_downgraded \
  --sponsorblock-mark sponsor,intro,outro \
  --embed-chapters \
  --sleep-interval 5 \
  --verbose
```

## Future Recommendations

1. Consider adding batch download support with automatic rate limiting
2. Explore PO Token generation/caching mechanisms
3. Add support for more SponsorBlock categories
4. Implement download queue management
5. Add progress bars for long downloads

## Version Info

- **yt-dlp**: 2025.11.12+
- **Python**: 3.10+
- **Deno**: 2.0.0+ (recommended)
- **Script Version**: Updated 2025-11-21
