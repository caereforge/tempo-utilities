# GitHub Actions relay for Tempo

A small Python relay that lets Tempo receive events from GitHub Actions
(or any other GitHub webhook) despite Tempo's IngestionServer being
LAN-only by design.

## Why this exists

Tempo's `com.github.actions` bundled score handles **rendering** of
GitHub events on the timeline (workflow runs, pushes, PRs, issues,
releases). But the events themselves come from `github.com` — the
public internet, not your LAN. Since the Tempo IngestionServer binds
loopback or LAN-only and is not designed to face the internet directly,
something has to bridge the gap.

This relay is that bridge:

```
github.com webhooks
       ↓ (HTTPS)
your public tunnel  (Cloudflare Tunnel / Tailscale Funnel / ngrok / your DDNS)
       ↓ (HTTPS → localhost)
this relay, listening on 127.0.0.1:7777
       ↓ (HTTP loopback)
Tempo IngestionServer on 127.0.0.1:7776
```

The relay verifies the `X-Hub-Signature-256` HMAC on every request,
translates the GitHub payload into a Tempo event, and forwards it with
the Tempo per-provider token (loaded from Keychain — never on disk).

## What you need

- macOS 15+ (the same target Tempo supports)
- Tempo installed and the `com.github.actions` bundled score available
- A public tunnel of your choice pointing at `localhost:7777`. Common
  picks: [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/),
  [Tailscale Funnel](https://tailscale.com/kb/1223/funnel), ngrok, or a
  reverse-proxy you already operate
- A GitHub repo or org you can configure webhooks on

If you have no tunnel and don't want one, this isn't the integration for
you — the events would have nowhere to enter from. Drop the GitHub
Actions score or rig your own polling layer.

## Setup

### 1. Bring up your tunnel

Whatever tunnel you prefer, route a public hostname (e.g.
`webhooks.example.com`) to `http://localhost:7777`. Test it from a
remote machine:

```bash
curl -sI https://webhooks.example.com/health
# expects: HTTP/2 200, body "tempo-gh-relay ok"
```

Hold off — the relay isn't running yet. The 200 will come after step 4.

### 2. Generate a webhook secret

Any sufficiently long random string. Example:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

You'll paste this both into GitHub and into Keychain. Don't lose it.

### 3. Store secrets in Keychain

The relay reads two secrets at startup. Replace the placeholders with
your actual values:

```bash
# The HMAC secret you generated above
security add-generic-password \
  -s tempo-gh-relay -a webhook-secret \
  -w '<HMAC secret>'

# The per-provider Tempo token (Tempo → Settings → Ingestion →
# create a token bound to provider "com.github.actions")
security add-generic-password \
  -s tempo-ingestion -a com.github.actions \
  -w '<Tempo per-provider token>'
```

Verify:

```bash
security find-generic-password -s tempo-gh-relay -a webhook-secret -w
security find-generic-password -s tempo-ingestion -a com.github.actions -w
```

Both should print the value back. If either is missing, the relay will
exit on launch with a clear keychain-miss error.

### 4. Install the LaunchAgent

This folder contains a template plist:
`com.example.tempo-gh-relay.plist`. Copy and customize it:

```bash
mkdir -p ~/Library/LaunchAgents
cp com.example.tempo-gh-relay.plist \
   ~/Library/LaunchAgents/com.example.tempo-gh-relay.plist
$EDITOR ~/Library/LaunchAgents/com.example.tempo-gh-relay.plist
```

Edit the two `/path/to/...` placeholders inside the plist to point at
where `relay.py` actually lives on your disk. Save, then load:

```bash
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.tempo-gh-relay.plist
launchctl enable gui/$(id -u)/com.example.tempo-gh-relay
launchctl kickstart -k gui/$(id -u)/com.example.tempo-gh-relay
```

(If you prefer a different label than `com.example.tempo-gh-relay`,
rename both the file and the `<key>Label</key>` value inside it.)

Confirm:

```bash
launchctl print gui/$(id -u)/com.example.tempo-gh-relay | head -5
tail -f /tmp/tempo-gh-relay.log
# expects: tempo-gh-relay listening on 127.0.0.1:7777 → http://127.0.0.1:7776/ingest
```

### 5. Configure the GitHub webhook

On your repo (or organization) → **Settings → Webhooks → Add webhook**:

- **Payload URL**: your tunnel hostname plus `/gh` (e.g.
  `https://webhooks.example.com/gh`)
- **Content type**: `application/json`
- **Secret**: the HMAC secret from step 2 (must match exactly)
- **Which events**: pick from the events the relay handles —
  `Workflow runs`, `Pushes`, `Pull requests`, `Issues`, `Releases`.
  Avoid "Send me everything" unless you actually want everything; most
  high-volume noise events are ack-only on the relay side and won't
  appear in Tempo, but they still cost a delivery.
- **Active**: yes
- Save

GitHub will immediately send a `ping` event. If signature and routing
are healthy you'll see a "✓ Last delivery successful" badge and a new
event in Tempo titled `<repo>: webhook ping`.

## Events the relay translates

| GitHub event       | When forwarded                                | Severity in Tempo |
|--------------------|-----------------------------------------------|-------------------|
| `ping`             | Always (the webhook config probe)             | info              |
| `push`             | When commits > 0                              | info              |
| `pull_request`     | `opened`, `reopened`, `closed`, `ready_for_review` | info       |
| `issues`           | `opened`, `reopened`, `closed`                | info              |
| `workflow_run`     | `completed` only; failure → error severity    | info / error      |
| `release`          | `published`, `released`                       | info              |

Other events (or sub-actions) are ack-only — the relay returns 204 to
GitHub so the delivery is marked successful, but nothing is forwarded
to Tempo. This keeps the timeline focused.

## Configuration via environment variables

All values are sensible defaults; override only if your setup is unusual:

| Variable                  | Default                          | Purpose                                       |
|---------------------------|----------------------------------|-----------------------------------------------|
| `TEMPO_GH_RELAY_HOST`     | `127.0.0.1`                      | Bind address for the relay                    |
| `TEMPO_GH_RELAY_PORT`     | `7777`                           | Bind port for the relay                       |
| `TEMPO_INGEST_URL`        | `http://127.0.0.1:7776/ingest`   | Where to forward translated events            |
| `TEMPO_GH_PROVIDER_ID`    | `com.github.actions`             | Tempo providerIdentifier on outgoing events   |
| `TEMPO_GH_TOKEN_ACCOUNT`  | same as `TEMPO_GH_PROVIDER_ID`   | Keychain account name holding the Tempo token |

Set them in the plist's `EnvironmentVariables` block if you need them
under launchd.

## Troubleshooting

**`keychain miss: service=tempo-gh-relay …`** — you skipped step 3 or
mistyped the service/account. Re-run `security add-generic-password`.

**GitHub Recent Deliveries shows `401 missing signature`** — the relay
got the request but no `X-Hub-Signature-256` header. Make sure the
webhook content-type is `application/json` (not URL-encoded) and that
the secret is set in GitHub.

**GitHub shows `401 bad signature`** — the secret on GitHub doesn't
match the one in Keychain. Regenerate, save in both places.

**GitHub shows timeouts / connection refused** — the relay isn't
running, or your tunnel isn't pointing at `localhost:7777`. Check
`launchctl print` and tail `/tmp/tempo-gh-relay.log`.

**Relay says `tempo unreachable`** — Tempo IngestionServer isn't
listening on `127.0.0.1:7776`. Verify Tempo is running and that the
IngestionServer is enabled in Settings.

**Events come through but appear with wrong styling in Tempo** — the
`com.github.actions` score must be installed. It's bundled with Tempo
v1, but if you've removed it for some reason, re-install from Settings
→ Sources.

## License

Same as the rest of `tempo-utilities` — see the LICENSE at the repo root.
