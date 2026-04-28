# Tempo Utilities

Helper utilities that complement [Tempo](https://tempoapp.app) — the
native macOS event hub. Shortcuts, scripts, and small tools that fit into
the workflows Tempo enables, without belonging to the app itself.

## What lives here

- **Shortcuts** — macOS Shortcuts that solve small workflow gaps, like
  "copy a deep link to the email I just selected". One-click install,
  hotkey-friendly.
- *(future)* **Scripts** — bash/Python helpers for polling-based score
  integrations (Pi-hole, Vaultwarden, etc.) when those grow beyond the
  inline snippets in `tempo-scores`.
- *(future)* **PopClip extensions**, **Hazel rules**, **Service workflows**
  — same spirit, different mechanisms.

## Why a separate repo

`tempo-scores` is the catalog of event-source definitions (JSON files
that teach Tempo how to render a source). This repo is for **everything
else** — utilities that live alongside Tempo without being a score.
Different shape, different review concerns, different distribution.

## Installing utilities

Each utility has its own folder under `shortcuts/`, `scripts/`, etc.
Open the folder's README for installation steps.

In general:

- **Shortcuts**: double-click the `.shortcut` file (or click an iCloud
  share link from the README) → Shortcuts.app opens an install sheet →
  Add. Optional hotkey via Shortcuts.app → ⓘ panel → Esegui con.
- **Scripts**: copy the snippet from the README into your shell, edit
  the config block, run from cron / launchd.

## Contributing

Open a PR with:
- A new folder under the appropriate top-level directory
- A README explaining what the utility does, install steps, and any
  required config or permissions
- The actual file (`.shortcut`, `.sh`, etc.) or, when distribution is
  link-based, the link in the README

Reviews happen as time allows — Tempo is free, and curating utilities
is a labor of love. If you need something urgently, fork and ship from
your own copy.

## Responsibility

> The functional responsibility of a utility lies with its author. Team
> review is a sanity check, not a warranty. Utilities run with your
> user's permissions; read the README before installing.

## License

MIT. See [LICENSE](./LICENSE). Covers utility files in this repo only,
not Tempo itself.
