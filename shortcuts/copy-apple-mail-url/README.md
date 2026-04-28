# Copy Apple Mail URL

A macOS Shortcut that copies a `message://` deep link to the selected
email in Apple Mail. Paste the link into a calendar event's notes (or
anywhere else you want a clickable reference), and Tempo will surface
it as an **Open email in Mail** action.

Apple Mail doesn't ship a "Copy as Link" command — this shortcut fills
that gap with ~20 lines of AppleScript.

## Install

### Option A — iCloud share link (one click)

> _iCloud share link will be added in a follow-up commit. Until then,
> use Option B._

### Option B — recreate manually (always works)

1. Open **Shortcuts.app**
2. Click **+** to create a new shortcut, name it `Copy Apple Mail URL`
3. Drag in **Esegui AppleScript** (Run AppleScript)
4. The action wants an input source — pick **App in uso** (Active app).
   The script ignores it; this just satisfies the slot
5. Paste the script below into the AppleScript editor:

   ```applescript
   tell application "Mail"
       set msgs to selection
       if (count of msgs) is 0 then
           display dialog "Nessuna email selezionata" buttons {"OK"} default button 1
           return
       end if
       set m to item 1 of msgs
       set msgID to message id of m
       set encodedID to do shell script "python3 -c 'import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))' " & quoted form of msgID
       set theURL to "message://%3C" & encodedID & "%3E"
       set the clipboard to theURL
       display notification theURL with title "Mail link copied"
       return theURL
   end tell
   ```

6. **Don't enable** "Usa come azione rapida" / "Menu Servizi" — those
   route the shortcut through the Services subsystem which Mail.app
   can't satisfy (mail messages aren't a Service-eligible selection).
   Keep the shortcut as a regular shortcut
7. Click the **ⓘ** info panel and assign a hotkey under **Esegui con** —
   suggestion: `⌃⌥⌘L` (L for Link), low conflict probability

## Permissions

The first time you trigger the hotkey, macOS will prompt:

> "Shortcuts wants access to Mail.app"

Accept. If you accidentally deny, re-grant under
**System Settings → Privacy & Security → Automation → Shortcuts**, ensure
**Mail** is checked.

## Use

1. In Mail.app, select an email
2. Press your hotkey (e.g. `⌃⌥⌘L`)
3. The notification "Mail link copied" appears with the URL preview
4. Paste the URL anywhere — calendar event notes, a Tempo event payload,
   a Hookmark hookable item, etc.

When the URL ends up in the notes of an event Tempo reads, Tempo
automatically generates an **Open email in Mail** action button on that
event.

## Limitations

- **Apple Mail only.** `message://` is Apple Mail's native scheme on
  macOS; other clients (MailMate, AirMail, Spark, Postbox) use their
  own. If you've copied a link from one of those, it's already a
  one-click deep link — no shortcut needed.
- **English UI assumed.** The dialog text is in Italian
  ("Nessuna email selezionata") in the example because that's the
  author's locale. Translate freely.
- **Python 3 dependency.** The shortcut uses `python3` for URL encoding,
  which ships with macOS as part of the developer tools. If `python3 -c`
  fails on your system, install Xcode Command Line Tools
  (`xcode-select --install`) or rewrite the encoding step to use AppleScript-only.

## Why this lives here, not in tempo-scores

`tempo-scores` is the catalog of **score** files (JSON definitions that
teach Tempo about a source). This shortcut is a **utility** — it doesn't
define a Tempo source, it just produces inputs that Tempo (and many
other tools) can consume. Different shape, different home.

## License

MIT (see repo [LICENSE](../../LICENSE)).
