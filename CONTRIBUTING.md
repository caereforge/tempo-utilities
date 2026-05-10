# Contributing a utility

Thanks for considering a contribution. This document explains how to submit a utility (Shortcut, script, helper tool) and what the review looks for.

## What belongs here

This repo hosts **utilities that fit alongside Tempo**, not source-of-event definitions. Examples:

- **Shortcuts** — macOS Shortcuts that solve workflow gaps adjacent to Tempo (deep-link copying, quick capture, glue between Tempo and another Mac app)
- **Scripts** — bash/Python helpers for polling-based score integrations (when a tool doesn't have a webhook and a small poller is the cleanest bridge)
- **PopClip extensions, Hazel rules, Service workflows, Keyboard Maestro macros** — same spirit, different mechanisms

What does **not** belong here:

- **Scores** — event-source definitions live in [`caereforge/tempo-scores`](https://github.com/caereforge/tempo-scores)
- **Patches to Tempo itself** — Tempo source is off-GitHub by policy
- **Standalone apps** — too large for this catalog; if it warrants its own repo, propose it via GitHub Discussions first

## The flow

1. Fork this repo.
2. Add your utility under the appropriate top-level directory (`shortcuts/`, `scripts/`, etc.). Create the directory if it doesn't exist yet.
3. Include a `README.md` in your utility's folder covering:
   - **What it does** — one paragraph, plain language
   - **Install steps** — concrete commands or click-paths
   - **Required permissions** — accessibility, automation, file access, network access if any
   - **Configuration** — environment variables, token paths, hardcoded values to swap before use
4. Add the actual file (`.shortcut`, `.sh`, `.py`, etc.) or, when distribution is link-based (iCloud Shortcut share), the link in the README.
5. Open a pull request. In the PR body include:
   - **What it's for** — which workflow gap it fills
   - **Sample usage** — paste the command you'd run, or describe the click-path
   - **Anything non-obvious** — quirks, OS version requirements, dependencies on other Mac apps

A reviewer will run the rubric below and either merge or leave comments with concrete criteria to address.

## Review rubric

Every utility is checked against these criteria before merge. The list is public so you can self-check before submitting.

### Security

- [ ] No hardcoded credentials. Tokens, API keys, and secrets must be parameterized (env vars or config files), never inlined.
- [ ] No silent network calls to third-party endpoints beyond what the README documents. If the utility POSTs to `localhost:7776/ingest` (i.e. Tempo itself), that's expected and welcome; anything else needs explanation.
- [ ] No destructive operations without explicit user opt-in (no `rm -rf`, `git push --force`, mass delete, etc. without a confirmation gate or clear documentation).
- [ ] Shortcuts that run shell scripts include the script's full content inline in the README (so reviewers don't have to chase external links).

### Functional

- [ ] The utility actually works as described on a current macOS version (state which version you tested on).
- [ ] If the utility integrates with Tempo, the events it produces have a clear `providerIdentifier` (reverse-DNS style: `com.author.utility-name`) and reasonable `metadata` fields.
- [ ] Scripts have a shebang line and handle missing dependencies gracefully (or document them in README).
- [ ] Shortcuts use named variables instead of position-bound magic — easier for someone else to adapt.

### Documentation

- [ ] README explains the workflow gap the utility addresses (the "why"), not just the steps (the "how").
- [ ] Required permissions are listed exhaustively. Users who decline a permission shouldn't be left guessing why the utility broke.
- [ ] If the utility needs configuration (a token, a path, a target host), the README lists every value the user must change before running.

## Sanitize before submitting

A contributed utility becomes public the moment the PR opens. Before pushing, check for:

- **Hardcoded tokens** in scripts or Shortcut steps — strip them, leave a placeholder like `<your-tempo-token>` and document the field
- **Hostnames or IPs from your own network** — use `your-mac.local` / `192.0.2.0/24` (TEST-NET-1, RFC 5737) as documentation placeholders
- **Filesystem paths that reveal your username or directory structure** — use `~/Documents/example/` style instead
- **Personal context in Shortcuts** — variable names like "MyHomeNAS" or "WorkLaptop" are fine, but full paths and credentials in Shortcut steps need to be removed
- **PII** in sample data — invent realistic-but-fake values

Sanitization is both a security ask and a practical one: a utility is meant to be reusable, so it shouldn't carry your specific environment.

## Responsibility

> The functional responsibility of a contributed utility lies with its author. Team review is a security and sanity check, not a warranty.

If a merged utility later breaks (macOS update, app version change, deprecated API), open an issue or a follow-up PR — the author is the natural maintainer.

## Review timing

Reviews happen as time allows. Tempo is free, and curating this catalog is a labor of love — not a full-time job. If you need a utility urgently for your own use, just keep it local — nothing prevents you from installing your own Shortcut or running your own script without going through this catalog.

## Questions

Open a GitHub Discussion or drop a message in the Tempo Discord — those are the channels where contributor threads live and stay searchable.
