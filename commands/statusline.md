---
name: statusline
description: Pick and order status-line items per line, choose a preset, toggle colors, or reset, with a live preview (like Codex /statusline)
argument-hint: "[--clear | preset NAME | line1=dir,git,model,ctx ...]"
allowed-tools: Bash, AskUserQuestion
---

# Configure the limitline status line

Help the user choose what each status-line line shows. The command edits only `preset`,
`line1` ... `line9` and `colors` in `~/.config/limitline/config.toml` (or the file
`LIMITLINE_CONFIG` names), keeps every other setting and comment, and saves the previous
file as `config.toml.bak`. Do not edit `~/.claude/settings.json`.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command. Call it `$SCRIPT`.
2. If the user passed arguments (`$ARGUMENTS`), act on them directly and skip the questions:
   - `--clear`: run `"$SCRIPT" statusline --clear`.
   - `preset NAME`: run `"$SCRIPT" statusline set preset=NAME`.
   - `KEY=VALUE ...` (for example `line1=dir,git,model,ctx colors=off`): run `"$SCRIPT" statusline set KEY=VALUE ...`.
   Then show the preview it prints and stop.
3. Otherwise run `"$SCRIPT" statusline list` and `"$SCRIPT" statusline preview`. Show the user the current line (the preview) and the item list in a short table: item, what it shows, Codex name.
4. Ask with AskUserQuestion, one question at a time:
   1. "Start from a preset?" options: `minimal` (folder, git, model, context), `default` (today's line), `full` (two lines, everything Claude Code sends), `pharos` (five lines with Pharos), `keep current`.
   2. "Which items on line 1, in order?" Offer the useful ids as a multi-select (`dir`, `project`, `git`, `model`, `effort`, `ctx`, `5h`, `7d`, `cost`, `vitals`, `tokens`, `title`, `version`, `pr`). Order follows the user's answer; if they type an order, use that.
   3. "Add a second line?" (no / yes, then the same item question for line 2). Repeat for more lines only if asked. `used`, `today`, `older` and `hosts` are whole Pharos lines.
   4. "Colors?" on / off.
5. Build the arguments, for example `preset=full line1=dir,git,model,ctx line2=5h,7d,cost colors=on`, and run `"$SCRIPT" statusline preview <arguments>` first. Show that preview and ask "Save this?" (save / change / cancel).
6. On save, run `"$SCRIPT" statusline set <arguments>`. It prints where it saved, where the backup is, and the new preview. Tell the user Claude Code redraws the status line on the next update.

Codex item ids work too (`current-dir`, `git-branch`, `model-with-reasoning`, `context-remaining`, `five-hour-limit`, `weekly-limit`, `used-tokens`, `estimated-thread-cost`, `session-id`, `thread-title`, `codex-version`). `run-state`, `task-progress` and `thread-credits` are not available in Claude Code: say so if asked, with the reason `statusline list` prints.

If a command exits non-zero, quote its message (it names the unknown item or key) and ask again. If it prints a traceback, quote it and stop.

```bash
"$SCRIPT" statusline list
"$SCRIPT" statusline preview line1=dir,git,model,ctx
"$SCRIPT" statusline set line1=dir,git,model,ctx
"$SCRIPT" statusline --clear
```
