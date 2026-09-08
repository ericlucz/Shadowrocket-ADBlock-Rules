---
name: awesome-claude-code
description: Look up community Claude Code resources — skills, subagents, slash commands, hooks, status lines, plugins, MCP servers and tooling — from the curated "Awesome Claude Code" list. Use when the user asks what skill/plugin/tool/agent exists for a task, asks for recommendations for their Claude Code setup, or wants to discover community resources rather than build one from scratch.
---

# Awesome Claude Code (resource finder)

`hesreallyhim/awesome-claude-code` is a hand-picked index of Claude Code resources.
It is a **link directory, not a skill pack** — there is nothing to run locally, so this
skill fetches the list on demand instead of vendoring a stale copy.

## How to use it

1. Fetch the list (WebFetch, or `curl -sSL`):
   - Main index: `https://raw.githubusercontent.com/hesreallyhim/awesome-claude-code/main/README.md`
   - Machine-readable table: `https://raw.githubusercontent.com/hesreallyhim/awesome-claude-code/main/THE_RESOURCES_TABLE_NEW.csv`
   - Legacy entries: the `README_ALTERNATIVES/` directory in the same repo
2. Search it for what the user needs. The list is organised by category:
   workflows & knowledge guides, tooling, status lines, hooks, slash commands,
   CLAUDE.md files, subagents, skills, plugins, and official Anthropic resources.
3. Report the 2–5 best matches with repo URL and a one-line summary each.
   Say when nothing on the list actually fits — do not stretch a match.

## Rules

- Always give the source repo URL so the user can vet it themselves.
- Entries are third-party and unvetted by Anthropic. Before suggesting the user
  install anything (especially hooks, which execute shell commands), say so, and
  read the resource's own source before running it.
- Do not copy large sections of the list into the repo: it is licensed
  CC BY-NC-ND 4.0 (attribution, non-commercial, no derivatives).

## Attribution

Awesome Claude Code © hesreallyhim — <https://github.com/hesreallyhim/awesome-claude-code>
Licensed CC BY-NC-ND 4.0. This skill links to that list; it does not redistribute it.
