---
name: yt-dlp-smart-downloader
description: Use when the user wants to download one or more videos or audio files with yt-dlp, compare available sizes or resolutions before downloading, run parallel downloads with parallel workers, or repair the final media file with ffmpeg and clean up the output filename.
---

# yt-dlp-smart-downloader

## Overview

This skill handles real-world `yt-dlp` download requests end to end: inspect formats first, let the user choose only when size tradeoffs are significant, always use parallel workers for download execution, optionally repair the container with `ffmpeg`, and leave behind clean final filenames.

Default assumption: the user wants the task completed, not just command suggestions. Run commands when possible and only ask brief follow-up questions when a choice has meaningful consequences.

## When To Use

Use this skill when the user asks to:

- download a video or audio file with `yt-dlp`
- inspect available sizes, resolutions, or format IDs before downloading
- batch download multiple URLs
- use parallel workers for parallel download work
- repair `MPEG-TS in MP4`, broken timestamps, or similar post-download container issues with `ffmpeg`
- rename downloaded files to human-friendly titles

## Workflow

### 1. Build context first

- Check whether `yt-dlp` is available with `which yt-dlp`.
- If `yt-dlp` is missing, install it before doing anything else.
- If the request may need repair or remuxing, check whether `ffmpeg` exists with `which ffmpeg`.
- Download into `"$HOME/Downloads"` by default unless the user explicitly requests another destination.
- Quote URLs and file paths carefully. Many media URLs contain `?`, `&`, or other shell-sensitive characters.

### 2. Decide whether to ask before downloading

Ask the user to choose first when:

- the user explicitly says to choose from available sizes or qualities
- any practical candidate format is larger than `200 MB`
- the site exposes several format IDs and the tradeoff is meaningful

Do not ask first when:

- the user already specified a quality such as `720p`, `1080p`, `best`, or `audio only`
- there is only one practical downloadable option
- you are continuing an existing thread where the user's preference is already clear

If all practical choices are `200 MB` or smaller, prefer completing the download directly without asking.

When asking for a choice, present a short table or bullet list with:

- resolution
- format ID
- approximate size if available
- whether it is a direct video+audio file or an HLS stream

If there are many choices, prefer showing the most practical ones rather than dumping every format line.

### 3. Inspect formats

Use `yt-dlp -F "<url>"` to list formats.

Prefer formats that make user choice easier:

- HLS entries with clear size estimates are often better for comparison
- Direct `https` MP4 entries can be a good fallback when HLS temporarily fails

If you need to summarize multiple URLs, do it one URL at a time and then present the options side by side.

### 4. Download strategy

For a single URL:

- use the user-selected format ID if one was chosen
- otherwise choose the closest match to the user's requested resolution

For downloads:

- always use parallel workers for the actual download work so multiple items can run concurrently and the main agent stays unblocked
- for one URL, a single worker may handle the full download
- for multiple URLs, prefer one worker per URL
- each worker should own only its assigned URL(s) and output files

Useful patterns:

```bash
yt-dlp -F "<url>"
DOWNLOAD_DIR="$HOME/Downloads"
yt-dlp -f "<format_id>" -P "$DOWNLOAD_DIR" "<url>"
yt-dlp -P "$DOWNLOAD_DIR" "<url1>" "<url2>"
yt-dlp -x --audio-format mp3 -P "$DOWNLOAD_DIR" "<url>"
```

### 5. Repair and finalize

If `yt-dlp` warns about container issues such as `Possible MPEG-TS in MP4 container`, repair the output with `ffmpeg`.

Preferred repair flow:

1. Keep the original file unless the user explicitly asks to keep only the repaired version.
2. Create a repaired copy with stream copy, not re-encoding:

```bash
ffmpeg -i "<input>" -c copy -movflags +faststart "<output>"
```

3. If the user wants only the repaired version, move the repaired file into the final desired filename and remove or replace the original only after the repaired file is confirmed to exist.

See [references/naming-and-fixups.md](references/naming-and-fixups.md) for filename cleanup and finalization rules.

### 6. Filename rules

- Use the source video title as the final filename by default.
- Do not append site identifiers, video IDs, or keys in square brackets unless the user explicitly requests them, the source title is unavailable, or a collision must be resolved.
- Sanitize illegal filename characters such as `/`.
- If a title contains problematic characters, replace them conservatively rather than inventing a brand-new title.
- If the user wants a simpler name, honor that request directly.

## Communication Rules

- Give short progress updates while downloads are running.
- When using parallel workers, tell the user you are parallelizing the work and what each agent is doing.
- When a choice is needed, ask one concise question with concrete options.
- Be explicit about assumptions, especially when carrying forward a preference like `720p`.

## Output Summary

When a download completes, report:

- final file path
- final file size
- selected format or resolution
- whether the file was repaired with `ffmpeg`
- whether the original file was kept or removed
