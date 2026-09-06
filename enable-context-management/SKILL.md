---
name: enable-context-management
description: Enable and verify Codex's experimental context management mode. Use when the user asks to enable or diagnose the `features.context_management.experimental_mode` setting.
---

# Enable Context Management

Enable `features.context_management.experimental_mode` without changing unrelated Codex configuration.

## Workflow

1. Resolve the user-level configuration path as `${CODEX_HOME:-$HOME/.codex}/config.toml`. Do not use project-local `.codex/config.toml` for this setting.

2. Confirm the file exists and inspect only the relevant feature sections. Do not print the complete config because it may contain credentials.

3. Before changing an existing file, create a same-directory backup with a timestamp, for example `config.toml.bak.YYYYMMDD-HHMMSS`.

4. Update the existing `[features.context_management]` table if present. Otherwise add exactly one such table with:

   ```toml
   [features.context_management]
   experimental_mode = true
   ```

   If the key already exists, update only its value. Never create duplicate TOML tables or modify unrelated keys.

5. Validate TOML syntax with a parser, then re-read the parsed value and require it to be the boolean `true`. If the installed Codex CLI exposes the feature, also check `codex features list` without dumping the whole configuration.

6. Tell the user to fully quit and reopen Codex, then start a new task/thread so the configuration is loaded. Existing tasks may not hot-load feature settings.

## Guardrails

- Do not modify project files, code, or unrelated Codex settings.
- Do not overwrite the original before the timestamped backup succeeds.
- Do not add the setting if the configuration path cannot be resolved or the TOML cannot be safely updated; report the blocker instead.
- Do not print the complete `config.toml` or expose credentials while verifying the change.
