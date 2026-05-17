#!/usr/bin/env python3
"""
tempo-gh-relay
--------------
Receives GitHub webhooks, verifies X-Hub-Signature-256 HMAC, translates the
payload to a Tempo event, and POSTs it to the local IngestionServer with
X-Tempo-Token auth.

Listens on 127.0.0.1:7777 (loopback only). Pair this with a public tunnel
(cloudflared / Tailscale Funnel / ngrok / anything) that routes your chosen
public hostname → 127.0.0.1:7777, then point your GitHub webhooks at that
hostname. The Tempo IngestionServer remains LAN-bound; only the tunnel is
public-facing.

Setup (full walkthrough in README.md alongside this file):

  1. Bring up a public tunnel pointing to localhost:7777
  2. Configure a webhook on your GitHub repo / org pointing to your tunnel
     hostname, content-type application/json, with a strong shared secret
  3. Store the secrets in macOS Keychain:
       security add-generic-password \\
         -s tempo-gh-relay -a webhook-secret -w '<HMAC secret>'
       security add-generic-password \\
         -s tempo-ingestion -a com.github.actions -w '<Tempo per-provider token>'
  4. Install the LaunchAgent (template in this folder) and load it

  Tempo bundled score "com.github.actions" handles rendering once events land.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
#
# All values can be overridden via environment variables for unusual setups.
# Defaults match a standard local Tempo install.

LISTEN_HOST = os.environ.get("TEMPO_GH_RELAY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("TEMPO_GH_RELAY_PORT", "7777"))
TEMPO_URL = os.environ.get("TEMPO_INGEST_URL", "http://127.0.0.1:7776/ingest")
PROVIDER_ID = os.environ.get("TEMPO_GH_PROVIDER_ID", "com.github.actions")

KEYCHAIN_SECRET_SERVICE = "tempo-gh-relay"
KEYCHAIN_SECRET_ACCOUNT = "webhook-secret"
KEYCHAIN_TOKEN_SERVICE = "tempo-ingestion"
# Keychain token account defaults to the provider id; can be overridden if
# you've stored the token under a different account name.
KEYCHAIN_TOKEN_ACCOUNT = os.environ.get("TEMPO_GH_TOKEN_ACCOUNT", PROVIDER_ID)


# ---------------------------------------------------------------------------
# Keychain helpers
# ---------------------------------------------------------------------------


def keychain_read(service: str, account: str) -> str:
    """Read a generic password. Exits non-zero if the entry is missing."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"keychain miss: service={service} account={account} "
            f"rc={result.returncode} err={result.stderr.strip()!r}\n"
        )
        sys.exit(2)
    return result.stdout.strip()


WEBHOOK_SECRET = keychain_read(KEYCHAIN_SECRET_SERVICE, KEYCHAIN_SECRET_ACCOUNT).encode()
TEMPO_TOKEN = keychain_read(KEYCHAIN_TOKEN_SERVICE, KEYCHAIN_TOKEN_ACCOUNT)


# ---------------------------------------------------------------------------
# GitHub → Tempo translation
# ---------------------------------------------------------------------------


def translate(event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Map a GitHub webhook event to a Tempo payload.
    Returns None if the event is uninteresting (a no-op that should be acked).
    """
    repo = payload.get("repository", {}).get("full_name", "?")
    actor = payload.get("sender", {}).get("login", "?")
    repo_url = payload.get("repository", {}).get("html_url", "")

    base_metadata: dict[str, Any] = {
        "repo": repo,
        "actor": actor,
        "githubEvent": event,
    }

    if event == "ping":
        return {
            "title": f"{repo}: webhook ping",
            "severity": "info",
            "eventType": "alert",
            "metadata": {**base_metadata, "zen": payload.get("zen", "")},
        }

    if event == "push":
        ref = payload.get("ref", "")
        branch = ref.rsplit("/", 1)[-1] if ref else "?"
        commits = payload.get("commits") or []
        n = len(commits)
        if n == 0:
            return None
        head = payload.get("head_commit") or {}
        first_line = (head.get("message") or "").splitlines()[0] if head else ""
        return {
            "title": f"{repo}: {n} commit{'s' if n != 1 else ''} to {branch}",
            "severity": "info",
            "eventType": "alert",
            "metadata": {
                **base_metadata,
                "branch": branch,
                "commits": str(n),
                "headMessage": first_line,
                "compareUrl": payload.get("compare", ""),
            },
        }

    if event == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request") or {}
        number = pr.get("number", "?")
        pr_title = pr.get("title", "")
        html_url = pr.get("html_url", "")
        if action not in ("opened", "reopened", "closed", "ready_for_review"):
            return None
        merged = pr.get("merged") is True
        suffix = "merged" if (action == "closed" and merged) else action
        return {
            "title": f"{repo}#{number} {suffix}: {pr_title}",
            "severity": "info",
            "eventType": "alert",
            "metadata": {
                **base_metadata,
                "prNumber": str(number),
                "prAction": action,
                "prUrl": html_url,
                "prMerged": str(merged).lower(),
            },
        }

    if event == "issues":
        action = payload.get("action", "")
        issue = payload.get("issue") or {}
        number = issue.get("number", "?")
        issue_title = issue.get("title", "")
        html_url = issue.get("html_url", "")
        if action not in ("opened", "reopened", "closed"):
            return None
        return {
            "title": f"{repo}#{number} issue {action}: {issue_title}",
            "severity": "info",
            "eventType": "alert",
            "metadata": {
                **base_metadata,
                "issueNumber": str(number),
                "issueAction": action,
                "issueUrl": html_url,
            },
        }

    if event == "workflow_run":
        action = payload.get("action", "")
        run = payload.get("workflow_run") or {}
        status = run.get("status", "")
        conclusion = run.get("conclusion")
        name = run.get("name", "workflow")
        html_url = run.get("html_url", "")
        if action != "completed":
            return None
        severity = "error" if conclusion == "failure" else "info"
        return {
            "title": f"{repo}: {name} {conclusion or status}",
            "severity": severity,
            "eventType": "alert",
            "metadata": {
                **base_metadata,
                "workflow": name,
                "conclusion": conclusion or "",
                "status": status,
                "runUrl": html_url,
                "branch": run.get("head_branch", ""),
            },
        }

    if event == "release":
        action = payload.get("action", "")
        release = payload.get("release") or {}
        tag = release.get("tag_name", "")
        html_url = release.get("html_url", "")
        if action not in ("published", "released"):
            return None
        return {
            "title": f"{repo}: released {tag}",
            "severity": "info",
            "eventType": "alert",
            "metadata": {
                **base_metadata,
                "tag": tag,
                "releaseUrl": html_url,
                "prerelease": str(release.get("prerelease", False)).lower(),
            },
        }

    # Events we haven't modeled yet: ack without forwarding.
    return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "tempo-gh-relay/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _respond(self, code: int, body: str = "") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        if body:
            self.wfile.write(body.encode())

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self._respond(200, "tempo-gh-relay ok\n")
            return
        self._respond(404, "not found\n")

    def do_POST(self) -> None:
        if self.path not in ("/", "/gh"):
            self._respond(404, "not found\n")
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 10 * 1024 * 1024:
            self._respond(400, "bad length\n")
            return
        raw = self.rfile.read(length)

        # HMAC verification
        sig_header = self.headers.get("X-Hub-Signature-256") or ""
        if not sig_header.startswith("sha256="):
            self._respond(401, "missing signature\n")
            return
        expected = hmac.new(WEBHOOK_SECRET, raw, hashlib.sha256).hexdigest()
        received = sig_header[len("sha256=") :]
        if not hmac.compare_digest(expected, received):
            self._respond(401, "bad signature\n")
            return

        event = self.headers.get("X-GitHub-Event") or ""
        delivery = self.headers.get("X-GitHub-Delivery") or ""

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._respond(400, "bad json\n")
            return

        tempo_payload = translate(event, payload)
        if tempo_payload is None:
            logging.info("ack-only: event=%s delivery=%s", event, delivery)
            self._respond(204)
            return

        # Add common fields
        tempo_payload.setdefault("providerIdentifier", PROVIDER_ID)
        tempo_payload.setdefault(
            "startDate",
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        tempo_payload.setdefault("metadata", {})["githubDelivery"] = delivery

        body_bytes = json.dumps(tempo_payload).encode("utf-8")
        logging.info("→ tempo body: %s", body_bytes[:500].decode("utf-8", "replace"))
        req = urllib.request.Request(
            TEMPO_URL,
            data=body_bytes,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body_bytes)),
                "X-Tempo-Token": TEMPO_TOKEN,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                if 200 <= resp.status < 300:
                    logging.info(
                        "forwarded: event=%s delivery=%s tempo=%d",
                        event,
                        delivery,
                        resp.status,
                    )
                    self._respond(resp.status, "forwarded\n")
                    return
                logging.warning(
                    "tempo %d: event=%s body=%s",
                    resp.status,
                    event,
                    body[:200].decode("utf-8", "replace"),
                )
                self._respond(502, f"tempo responded {resp.status}\n")
        except urllib.error.HTTPError as e:
            logging.warning(
                "tempo HTTPError %d: event=%s err=%s",
                e.code,
                event,
                e.read()[:200].decode("utf-8", "replace"),
            )
            self._respond(502, f"tempo HTTPError {e.code}\n")
        except Exception as e:
            logging.warning("tempo unreachable: event=%s err=%s", event, e)
            self._respond(502, f"tempo unreachable: {e}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    logging.info(
        "tempo-gh-relay listening on %s:%d → %s", LISTEN_HOST, LISTEN_PORT, TEMPO_URL
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
