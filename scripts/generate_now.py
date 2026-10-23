"""Generate `now.svg` — a neon terminal card of what BalalaikaDev is working on.

Pulls recent public activity from the GitHub API and renders it as a fake
terminal session in the Runi Shell palette, matching the profile's radar banner.
Designed to run in a scheduled GitHub Action; degrades gracefully to a static
card when the API is unavailable (e.g. offline), so it never breaks the README.

Usage: python scripts/generate_now.py [out.svg]
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
import urllib.request

USER = "BalalaikaDev"

# Runi Shell palette (same tokens as the radar banner)
BG = "#06070f"
PANEL = "#0a0b1a"
CYAN = "#18e0ff"
MAGENTA = "#ff2e97"
GREEN = "#00ff9c"
YELLOW = "#fcee0a"
TEXT = "#ccd6f0"
DIM = "#6e79a8"
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

WHOAMI = "Darius Genkinger — BI/data engineer · Electrical & Automation @ HAMK"


def _get_events() -> list[dict]:
    """Recent public events for USER, or [] if the API can't be reached."""
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=30",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile"},
    )
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except Exception as exc:  # offline, rate-limited, etc. — stay graceful
        print(f"warning: could not fetch events ({exc}); using fallback", file=sys.stderr)
        return []


def _repo(ev: dict) -> str:
    return ev.get("repo", {}).get("name", "").split("/")[-1]


def _activity_lines(events: list[dict], limit: int = 3) -> list[str]:
    """Turn raw events into short human log lines (newest first, de-duplicated)."""
    lines: list[str] = []
    seen: set[str] = set()
    for ev in events:
        t = ev.get("type")
        repo = _repo(ev)
        line = None
        if t == "PushEvent":
            n = len(ev.get("payload", {}).get("commits", []) or [])
            line = f"pushed {n} commit{'s' if n != 1 else ''} to {repo}"
        elif t == "PullRequestEvent":
            act = ev.get("payload", {}).get("action", "updated")
            num = ev.get("payload", {}).get("number", "")
            line = f"{act} PR #{num} in {repo}"
        elif t == "CreateEvent":
            ref = ev.get("payload", {}).get("ref_type", "ref")
            line = f"created {ref} in {repo}"
        elif t == "IssuesEvent":
            act = ev.get("payload", {}).get("action", "updated")
            line = f"{act} an issue in {repo}"
        elif t == "ReleaseEvent":
            line = f"published a release in {repo}"
        elif t == "WatchEvent":
            line = f"starred {repo}"
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _focus(events: list[dict]) -> str:
    """One-line 'currently' summary from the most recent push/PR."""
    for ev in events:
        if ev.get("type") in ("PushEvent", "PullRequestEvent"):
            return f"building in {_repo(ev)}"
    return "building out the portfolio — Runi OSINT & osintkit"


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def build(events: list[dict]) -> str:
    focus = _focus(events)
    activity = _activity_lines(events) or ["(quiet right now — check back soon)"]
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    W = 860
    pad = 22
    line_h = 26
    top = 70
    rows = [
        (CYAN, "balalaika@dev", "~ $ ", TEXT, "whoami"),
        (TEXT, "", "", GREEN, f"→ {WHOAMI}"),
        (CYAN, "balalaika@dev", "~ $ ", TEXT, "cat now.txt"),
        (TEXT, "", "", YELLOW, f"→ currently: {focus}"),
        (CYAN, "balalaika@dev", "~ $ ", TEXT, f"tail -n {len(activity)} activity.log"),
    ]
    for a in activity:
        rows.append((TEXT, "", "", DIM, f"  {a}"))
    rows.append((CYAN, "balalaika@dev", "~ $ ", MAGENTA, "_"))

    H = top + line_h * len(rows) + 34

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="{FONT}">']
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>')
    out.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="13" fill="{PANEL}" '
               f'stroke="{CYAN}" stroke-opacity="0.3"/>')
    # title bar
    out.append(f'<rect x="1" y="1" width="{W-2}" height="40" rx="13" fill="#0c0c1e"/>')
    for i, c in enumerate((MAGENTA, YELLOW, GREEN)):
        out.append(f'<circle cx="{24 + i*22}" cy="21" r="6" fill="{c}"/>')
    out.append(f'<text x="{W/2}" y="26" text-anchor="middle" font-size="12" '
               f'fill="{DIM}" letter-spacing="1">now — live activity</text>')

    y = top
    for prompt_c, host, sym, body_c, body in rows:
        x = pad
        if host:
            out.append(f'<text x="{x:.0f}" y="{y}" font-size="14" fill="{prompt_c}">{_esc(host)}</text>')
            x += len(host) * 8.4
            out.append(f'<text x="{x:.0f}" y="{y}" font-size="14" fill="{DIM}">{_esc(sym)}</text>')
            x += len(sym) * 8.4
        if body == "_":
            out.append(f'<text x="{x:.0f}" y="{y}" font-size="14" fill="{body_c}">_'
                       f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" '
                       f'repeatCount="indefinite"/></text>')
        else:
            out.append(f'<text x="{x:.0f}" y="{y}" font-size="14" fill="{body_c}">{_esc(body)}</text>')
        y += line_h

    out.append(f'<text x="{pad}" y="{H-14}" font-size="10" fill="{DIM}" '
               f'letter-spacing="1">updated {updated} · auto-generated from GitHub activity</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "now.svg"
    svg = build(_get_events())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {path}")
