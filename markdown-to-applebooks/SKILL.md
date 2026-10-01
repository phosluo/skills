---
name: markdown-to-applebooks
description: Convert a local Markdown file into an EPUB with pandoc and copy it into the user's Apple Books iCloud Documents folder. Use when the user asks to turn Markdown into an EPUB for Apple Books, send a note or article to Apple Books, export Markdown to Books, or automate the Markdown -> EPUB -> Apple Books workflow.
---

# Markdown To Apple Books

Use this skill when the user wants a local Markdown document turned into an EPUB and placed into Apple Books.

This skill is for a very specific workflow:
1. Find the Markdown file.
2. Convert it to EPUB with `pandoc`.
3. Resolve the Apple Books iCloud folder on the current machine.
4. Copy the EPUB into that folder.
5. Confirm the file exists in the destination.

Keep the workflow simple. Do not add extra formatting work unless the user asks for it.

## What To Do

### 1. Confirm the source file

Work from the Markdown file the user names. If they do not give a path, search the current workspace for likely `.md` files and make a reasonable guess from context.

If there are multiple plausible files and the choice is risky, ask one short clarifying question. Otherwise proceed.

### 2. Build the EPUB

Check whether `pandoc` is available:

```bash
which pandoc
```

If `pandoc` is present, convert the file directly. Write the EPUB next to the Markdown file unless the user asked for a different output path.
By default, write the generated EPUB to the current working directory:

```bash
$PWD
```

Do not scatter generated EPUB files beside arbitrary source Markdown files unless the user explicitly asks for that behavior.

Example:

```bash
pandoc /absolute/path/input.md \
  -f markdown+lists_without_preceding_blankline \
  -o "$PWD/input.epub" \
  --metadata title='Document Title'
```

Always pass `-f markdown+lists_without_preceding_blankline`. Obsidian and many
other Markdown editors start a list on the line right after a paragraph with no
blank line in between. Pandoc's default `markdown` reader treats those items as
continuations of the paragraph and silently merges the whole list into one
paragraph, which is invisible until someone reads the EPUB. The extension keeps
every other pandoc Markdown behavior (math, footnotes, tables) and only changes
how a list that follows text without a blank line is parsed.

Title selection rule:

1. Start from the filename as the default EPUB title.
2. Derive a clean human-readable title from the filename:
   - remove the `.md` extension,
   - replace hyphens and underscores with spaces,
   - collapse awkward separators,
   - convert obvious slug-style names into normal title case when that improves readability.
3. Then read the Markdown file and look for the first level-1 heading, a line that starts with `# `.
4. Use that heading only if it clearly looks like the document title rather than a section heading.
5. If the first level-1 heading looks generic or section-like, keep the filename-derived title.

Treat headings like these as section-like unless the user explicitly wants otherwise:
- `Introduction`
- `Intro`
- `Preface`
- `Foreword`
- `Chapter 1`
- `Part I`
- headings that end with `Introduction` in another language pair, such as `Introduction 引言`

Examples:
- `office-hours-skill-bilingual.md` -> `Office Hours Skill Bilingual`
- `my_notes_on_prompting.md` -> `My Notes On Prompting`
- `The Algorithm.md` with first heading `# Introduction 引言` -> `The Algorithm`

Do not block the workflow on perfect title generation. Pick a clean, reasonable title and continue.

If `pandoc` is missing, say so plainly and stop. Do not invent a fallback converter unless the user asks.

### 3. Resolve the Apple Books destination

Do not hardcode a username-specific path.

Start with the standard Apple Books iCloud path relative to the current home directory:

```bash
BOOKS_DIR="$HOME/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents"
```

Check that it exists before copying:

```bash
test -d "$BOOKS_DIR"
```

If it exists, use it.

If it does not exist, say so plainly and stop. Do not guess random alternatives unless the user asks.

### 4. Copy into Apple Books

Copy the generated EPUB there using the same filename unless the user asked for a rename.

Example:

```bash
cp /absolute/path/input.epub "$BOOKS_DIR/input.epub"
```

This path is often outside the writable sandbox. If the copy fails with a sandbox permission error, immediately rerun the copy with escalated permissions. Do not stop at the first failure.

### 5. Verify

Always verify the final file exists in Apple Books:

```bash
ls -lh "$BOOKS_DIR/input.epub"
```

If verification fails because of sandbox restrictions, rerun the verification with escalated permissions.

## Default Behavior

- Prefer the Markdown file the user most recently worked on when context makes that obvious.
- Keep the EPUB filename aligned with the Markdown filename.
- Put generated EPUB files in the current working directory by default.
- Preserve the original Markdown file.
- Do not move files, only copy the EPUB into Apple Books unless the user explicitly asks otherwise.
- Do not add cover images, CSS, or table-of-contents tuning unless requested.

## What To Report Back

Be concise. Tell the user:
1. which Markdown file was used,
2. where the EPUB was written, defaulting to the current working directory,
3. where it was copied in Apple Books,
4. whether verification succeeded.

If something failed, say exactly which step failed and why.
