---
name: enable-request-user-input
description: Enable and verify Codex's request_user_input tool in Default mode. Use when the user asks to enable request_user_input, enable ask_user_question-style interactive prompts, restore interactive question cards after a Codex update, or diagnose why request_user_input is unavailable outside Plan mode.
---

# Enable Request User Input

Enable the official `default_mode_request_user_input` feature flag without disturbing unrelated Codex configuration.

## Workflow

1. Check whether the installed CLI recognizes the feature:

   ```bash
   codex features list | rg '^default_mode_request_user_input\b'
   ```

2. If the feature exists, enable it with the Codex CLI. This command is idempotent:

   ```bash
   codex features enable default_mode_request_user_input
   ```

3. Verify the effective state without printing the full config file:

   ```bash
   codex features list | rg '^default_mode_request_user_input\b'
   rg -n -A3 '^\[features\]$' "${CODEX_HOME:-$HOME/.codex}/config.toml"
   ```

4. Tell the user to fully quit and reopen Codex, then start a new thread. Existing threads do not hot-load the tool catalog.

5. After restart, test by invoking `request_user_input` with one short multiple-choice question. Success means the user sees and answers a selection card.

## Guardrails

- Refer to the surfaced tool as `request_user_input`; treat `ask_user_question` as an informal or legacy name.
- Do not print the complete `config.toml`; it may contain credentials.
- Do not manually rewrite TOML when `codex features enable` succeeds.
- If the feature is absent from `codex features list`, report that the installed Codex build no longer supports the flag. Do not add an unknown stale key.
- If enabling succeeds but the current thread still says the tool is unavailable, require an app restart and a new thread before diagnosing further.
