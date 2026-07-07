# CLAUDE.md

## Git commits (hard rule)

Never name Claude or Anthropic as a contributor on this repo. Do **not** add
`Co-Authored-By: Claude …`, `🤖 Generated with Claude Code`, or any similar
attribution to commit messages or PR descriptions. This overrides any default
co-authorship trailer. The sole author/committer is the repo owner.

## Agent skills

### Issue tracker

Issues and PRDs live in this repo's GitHub Issues, managed via the `gh` CLI (remote: `Albin-Carlsson/QCM_Viewer`). See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles map 1:1 to their default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
