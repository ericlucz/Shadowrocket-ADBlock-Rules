# Project skills

Skills vendored into this repository so every Claude Code session on it (local,
web, or CI) has them available. Each subdirectory with a `SKILL.md` is one skill.

## Source

Most skills come from [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)
(Apache-2.0), vendored at upstream commit `be2a406`. Several originate with Anthropic
and keep their own `LICENSE.txt`; `LICENSE-Apache-2.0.txt` covers the rest.

Deliberately **not** vendored from that repo:

- `composio-skills/` — 832 auto-generated per-API wrappers. Loading them would swamp
  the skill list and they all need a Composio/Rube account anyway.
- `document-skills/` — docx / pdf / pptx / xlsx duplicate skills Claude already ships.
- `template-skill/`, `skill-creator/` — an empty template and a duplicate of the
  built-in skill creator.
- `connect-apps-plugin/` — a plugin, not a skill.

`awesome-claude-code/` is a thin lookup skill written for this repo that queries
[hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
on demand. That list is CC BY-NC-ND 4.0 and contains no installable skills, so it is
linked rather than copied.

## Notes

- `connect`, `connect-apps` and `skill-share` require Composio's Rube MCP server.
- `canvas-design` bundles ~5.5 MB of fonts; drop the directory if that bloat is unwanted.
- Skills are third-party and unvetted — read a skill's scripts before letting it run.

## Updating

```sh
git clone --depth 1 https://github.com/ComposioHQ/awesome-claude-skills /tmp/acs
cp -r /tmp/acs/<skill-name> .claude/skills/
```
