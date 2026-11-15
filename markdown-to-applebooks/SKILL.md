---
name: markdown-to-applebooks
description: Convert a local Markdown document into a single-file EPUB archive with resolved author metadata and an original content-related cover, then copy it into the user's Apple Books iCloud Documents folder. Use when the user asks to turn Markdown into an EPUB for Apple Books, send a note or article to Books, export Markdown to Books, or automate a Markdown-to-EPUB-to-Apple-Books workflow.
---

# Markdown To Apple Books

Turn a Markdown document into an Apple Books-ready EPUB. Resolve the book's identity before conversion: one original title, the correct author metadata, and a cover that belongs to this document. Deliver one standard single-file EPUB archive, never an exploded EPUB directory.

## Workflow

### 1. Find the source

Work from the Markdown file the user names. If no path is given, search the current workspace for likely `.md` files and choose the most obvious candidate from context.

If several files are plausible and choosing wrong would be disruptive, ask one short clarifying question. Otherwise proceed.

### 2. Resolve the title and author

**Title**

- Use an explicit title from YAML front matter when present.
- Otherwise use the first level-1 heading only if it reads as the document title rather than a section heading.
- Otherwise derive a clean title from the filename.
- Preserve the resolved title verbatim. Do not translate it, shorten it, or substitute a different-language title.
- The EPUB title and the cover title must be identical.

Treat headings such as `Introduction`, `Preface`, `Chapter 1`, or `Introduction 引言` as section headings unless the user says otherwise.

**Author**

- Use explicit author metadata from front matter or the document's byline when available.
- Otherwise inspect the opening pages, copyright page, ISBN, or source links.
- When the author is not established by the document, research the title and author online. Prefer publisher pages, library catalogs, Open Library, Google Books, and author sites.
- For a translation, summary, or adaptation, identify the original author unless the user specifically wants the translator or adapter credited.
- Keep all genuinely credited authors. Do not merge distinct people into one name.
- Never invent an author. If reasonable research does not settle it, ask one concise question. If the user does not know or does not care, use `Unknown`.

Do not block the conversion on title or author research when the source clearly supplies both.

### 3. Make the cover

Create an original cover for this document. Choose the visual direction, imagery, typography, and composition yourself; there is no required template or style.

The cover must:

- use the resolved title verbatim, in its original language;
- relate to the document's actual subject, argument, or story;
- remain legible at Apple Books thumbnail size;
- avoid invented publisher marks, awards, endorsements, or factual claims;
- not add a translated title or an alternate title that competes with the original.

The cover may include the author name and other visual text when useful, but none of it should change or replace the original title.

Write the cover to a local image file and inspect the result before embedding it. If the title is unreadable, cropped, or the image does not fit the content, revise the cover.

### 4. Build a single-file EPUB archive

The deliverable is one standard `.epub` file backed by a ZIP archive. Do not unpack it or place an exploded EPUB package directory in Apple Books.

Check that `pandoc` is available:

```bash
which pandoc
```

If `pandoc` is missing, say so plainly and stop. Do not invent a fallback converter unless the user asks.

Write the EPUB to the current working directory by default, using the Markdown filename as the EPUB filename unless the user asks for another name.

Pass the resolved title, author metadata, and cover image to pandoc:

```bash
pandoc /absolute/path/input.md \
  -f markdown+lists_without_preceding_blankline \
  --metadata title="$TITLE" \
  --metadata author="$AUTHOR" \
  --epub-cover-image=/absolute/path/cover.png \
  -o "$PWD/input.epub"
```

For multiple authors, use a temporary YAML metadata file with an `author` list, then pass it with `--metadata-file`. Keep the title and author values exactly as resolved.

Always pass `-f markdown+lists_without_preceding_blankline`. Obsidian and many other Markdown editors start a list on the line right after a paragraph with no blank line in between. Pandoc's default `markdown` reader treats those items as continuations of the paragraph and silently merges the whole list into one paragraph, which is invisible until someone reads the EPUB.

Pandoc writes the EPUB as a single ZIP-based file. Keep that file intact for delivery; do not unzip it into the Books folder.

### 5. Verify the EPUB

Before copying, confirm that:

- the EPUB file exists and is non-empty;
- the EPUB is one regular file, is a complete ZIP archive, and has `application/epub+zip` as its `mimetype`;
- the cover image is present in the EPUB and referenced by the package;
- the OPF title matches the resolved title exactly;
- the OPF author metadata matches the resolved author list;
- the cover displayed in the EPUB is the same image you inspected.

Useful checks include:

```bash
test -f "$EPUB" && test -s "$EPUB"
test "$(unzip -p "$EPUB" mimetype)" = "application/epub+zip"
unzip -t "$EPUB" >/dev/null
unzip -l "$EPUB"
unzip -p "$EPUB" EPUB/content.opf
```

If `epubcheck` is available, run it as an additional check. If the cover, title, or author is missing, fix the build before copying.

### 6. Copy into Apple Books

Do not hardcode a username-specific path. Resolve the standard Apple Books iCloud directory from the current home directory:

```bash
BOOKS_DIR="$HOME/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents"
test -d "$BOOKS_DIR"
```

If it does not exist, say so plainly and stop.

Copy the verified EPUB there using the same filename unless the user requested a rename. Before replacing an existing EPUB, preserve its Apple Books identity attributes. A plain `cp` over a regular macOS file clears extended attributes, which can make an existing book disappear from iCloud and other Apple Books devices.

Run the snapshot, replacement, restore, and verification in one shell so the saved values remain available:

```bash
set -euo pipefail

dest="$BOOKS_DIR/input.epub"
source_epub="/absolute/path/input.epub"

asset_id_hex=""
generation=""
title_hex=""
author_hex=""
genre_hex=""
supplemental_hex=""
fpfs_hex=""

if [ -L "$source_epub" ] || [ ! -f "$source_epub" ]; then
  echo "Source must be a single-file EPUB archive: $source_epub" >&2
  exit 1
fi
if [ "$(unzip -p "$source_epub" mimetype 2>/dev/null)" != "application/epub+zip" ]; then
  echo "Source is not a valid single-file EPUB archive: $source_epub" >&2
  exit 1
fi
if ! unzip -t "$source_epub" >/dev/null; then
  echo "Source EPUB ZIP is incomplete: $source_epub" >&2
  exit 1
fi

if [ -e "$dest" ]; then
  if [ -L "$dest" ] || [ ! -f "$dest" ]; then
    echo "Refusing to replace a non-file EPUB package: $dest" >&2
    exit 1
  fi

  asset_id_hex=$(xattr -px 'com.apple.iBooks.assetID#S' "$dest" 2>/dev/null || true)
  generation=$(xattr -p 'com.apple.iBooks.generation#S' "$dest" 2>/dev/null || true)
  title_hex=$(xattr -px 'com.apple.iBooks.title#S' "$dest" 2>/dev/null || true)
  author_hex=$(xattr -px 'com.apple.iBooks.author#S' "$dest" 2>/dev/null || true)
  genre_hex=$(xattr -px 'com.apple.iBooks.genre#S' "$dest" 2>/dev/null || true)
  supplemental_hex=$(xattr -px 'com.apple.iBooks.isSupplementalContent#S' "$dest" 2>/dev/null || true)
  fpfs_hex=$(xattr -px 'com.apple.fileprovider.fpfs#P' "$dest" 2>/dev/null || true)

  if [ -z "$asset_id_hex" ]; then
    echo "Refusing to overwrite: existing EPUB has no Books assetID." >&2
    exit 1
  fi
fi

cp "$source_epub" "$dest"

if [ -n "$asset_id_hex" ]; then
  xattr -wx 'com.apple.iBooks.assetID#S' "$asset_id_hex" "$dest"
  [ -z "$title_hex" ]  || xattr -wx 'com.apple.iBooks.title#S'  "$title_hex"  "$dest"
  [ -z "$author_hex" ] || xattr -wx 'com.apple.iBooks.author#S' "$author_hex" "$dest"
  [ -z "$genre_hex" ]  || xattr -wx 'com.apple.iBooks.genre#S'  "$genre_hex"  "$dest"
  [ -z "$supplemental_hex" ] || xattr -wx 'com.apple.iBooks.isSupplementalContent#S' "$supplemental_hex" "$dest"
  [ -z "$fpfs_hex" ]   || xattr -wx 'com.apple.fileprovider.fpfs#P' "$fpfs_hex" "$dest"

  case "$generation" in
    ''|*[!0-9]*) generation=1 ;;
  esac
  generation=$((generation + 1))
  xattr -w 'com.apple.iBooks.generation#S' "$generation" "$dest"
fi

touch "$dest"

cmp "$source_epub" "$dest"
if [ -n "$asset_id_hex" ]; then
  test "$(xattr -px 'com.apple.iBooks.assetID#S' "$dest")" = "$asset_id_hex"
  test -z "$title_hex"  || test "$(xattr -px 'com.apple.iBooks.title#S'  "$dest")" = "$title_hex"
  test -z "$author_hex" || test "$(xattr -px 'com.apple.iBooks.author#S' "$dest")" = "$author_hex"
  test -z "$genre_hex"  || test "$(xattr -px 'com.apple.iBooks.genre#S'  "$dest")" = "$genre_hex"
  test -z "$supplemental_hex" || test "$(xattr -px 'com.apple.iBooks.isSupplementalContent#S' "$dest")" = "$supplemental_hex"
  test -z "$fpfs_hex"   || test "$(xattr -px 'com.apple.fileprovider.fpfs#P' "$dest")" = "$fpfs_hex"
  test "$(xattr -p 'com.apple.iBooks.generation#S' "$dest")" = "$generation"
fi
ls -lh "$dest"
```

Incrementing `generation` tells Books that the existing asset has new content while retaining its identity. Refuse to replace directory-style EPUB packages or existing files without a Books `assetID`; use a different filename instead.

This path is often outside the writable sandbox. If a copy or attribute operation fails with a sandbox permission error, retry the same step with escalated permissions. Do not skip the attribute restore or verification.

If verification fails because of sandbox restrictions, rerun the verification with escalated permissions.

## Defaults

- Preserve the original Markdown file.
- Put the generated EPUB in the current working directory by default.
- Use the resolved title consistently in the EPUB metadata and on the cover.
- Keep the original title's language. Never put a translated title on the cover in place of the original.
- Add author metadata rather than leaving the book unattributed when reliable evidence exists.
- Make a new content-related cover for the document. The visual approach is yours.
- Deliver a single-file `.epub` ZIP archive. Never place an exploded EPUB directory in Apple Books.
- Do not add CSS or table-of-contents tuning unless the user asks.
- Do not move files; only copy the EPUB into Apple Books.
- When replacing an existing Books EPUB, preserve and verify its Books/iCloud identity attributes. Never treat a plain `cp` as a safe update.

## What To Report Back

Be concise. Tell the user:

1. which Markdown file was used;
2. the resolved title and author(s);
3. where the cover and single-file EPUB were written;
4. where the single-file EPUB was copied in Apple Books, and whether it was added or replaced;
5. whether the EPUB metadata, cover, Books identity attributes, and sync-safe replacement verification passed.

If something failed, say exactly which step failed and why.
