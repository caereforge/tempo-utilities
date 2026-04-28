# Shortcuts

macOS Shortcuts that fit into Tempo workflows. Each lives in its own
subfolder with a dedicated README, install instructions, and the
shortcut file or share link.

## Catalog

- [**Copy Apple Mail URL**](./copy-apple-mail-url/) — copies a `message://`
  deep link to the selected email. Paste the link into a calendar event's
  notes; Tempo surfaces it as an "Open email in Mail" action.

## Why Shortcuts

Tempo is read-only against your data sources — it shows what's there and
gives you action buttons, but it doesn't author content elsewhere.
Shortcuts fill the inverse gap: small, user-controlled scripts that
*produce* the inputs Tempo consumes (URLs, deep links, formatted text)
from apps that don't expose them natively.

The Mail URL shortcut is the founding example: Apple Mail doesn't have a
"Copy as Link" command, but EventKit and Tempo know how to handle a
`message://` URL once you have one. The shortcut bridges the gap.
