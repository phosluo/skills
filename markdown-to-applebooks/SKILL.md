---
name: markdown-to-applebooks
description: Convert a local Markdown document into an EPUB with resolved author metadata and an original content-related cover, then copy it into the user's Apple Books iCloud Documents folder. Use when the user asks to turn Markdown into an EPUB for Apple Books, send a note or article to Books, export Markdown to Books, or automate a Markdown-to-EPUB-to-Apple-Books workflow.
---

# Markdown To Apple Books

Turn a Markdown document into an Apple Books-ready EPUB. Resolve the book's identity before conversion: one original title, the correct author metadata, and a cover that belongs to this document.

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

### 4. Build the EPUB

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

### 5. Verify the EPUB

Before copying, confirm that:

- the EPUB file exists and is non-empty;
- the cover image is present in the EPUB and referenced by the package;
- the OPF title matches the resolved title exactly;
- the OPF author metadata matches the resolved author list;
- the cover displayed in the EPUB is the same image you inspected.

Useful checks include:

```bash
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

Copy the verified EPUB there using the same filename unless the user requested a rename:

```bash
cp /absolute/path/input.epub "$BOOKS_DIR/input.epub"
```

This path is often outside the writable sandbox. If the copy fails with a sandbox permission error, retry with escalated permissions. Then verify:

```bash
ls -lh "$BOOKS_DIR/input.epub"
```

If verification fails because of sandbox restrictions, rerun the verification with escalated permissions.

## Defaults

- Preserve the original Markdown file.
- Put the generated EPUB in the current working directory by default.
- Use the resolved title consistently in the EPUB metadata and on the cover.
- Keep the original title's language. Never put a translated title on the cover in place of the original.
- Add author metadata rather than leaving the book unattributed when reliable evidence exists.
- Make a new content-related cover for the document. The visual approach is yours.
- Do not add CSS or table-of-contents tuning unless the user asks.
- Do not move files; only copy the EPUB into Apple Books.

## What To Report Back

Be concise. Tell the user:

1. which Markdown file was used;
2. the resolved title and author(s);
3. where the cover and EPUB were written;
4. where the EPUB was copied in Apple Books;
5. whether the EPUB metadata and cover verification passed.

If something failed, say exactly which step failed and why.
