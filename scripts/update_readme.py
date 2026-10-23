"""Rewrite the auto-generated regions of README.md from GitHub.

Currently refreshes the "Selected projects" table (between the PROJECTS markers)
from the user's public repos, so adding or renaming a repo updates the README on
the next scheduled run. Curated descriptions override GitHub's for named repos,
and pinned rows (e.g. a "coming soon" project) are always appended.

Idempotent and safe offline: if the API can't be reached, README is left as-is.

Usage: python scripts/update_readme.py [README.md]
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request

USER = "BalalaikaDev"
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"

# Hand-written descriptions win over the repo's GitHub description, by repo name.
OVERRIDES = {
    "runi-os": "Self-hosted OSINT &amp; data platform — 45+ intelligence sources "
               "fused into one provenance-tracked Neo4j graph, an AI investigation "
               "engine, and a modular dashboard.",
}
# Rows always appended after the live repos.
PINNED_EXTRA = [
    ("_data pipeline_",
     "_Coming soon — an automated, self-refreshing analytics pipeline "
     "(ingest → model → forecast → dashboard)._"),
]
# Repos never shown (the profile repo renders this very README).
HIDE = {USER.lower()}


def _repos() -> list[dict]:
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/repos?sort=pushed&per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile"},
    )
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _row(repo: dict) -> str:
    name = repo["name"]
    url = repo.get("html_url", f"https://github.com/{USER}/{name}")
    desc = OVERRIDES.get(name)
    if not desc:
        desc = html.escape(repo.get("description") or "—", quote=False)
    meta = []
    if repo.get("language"):
        meta.append(f"`{repo['language']}`")
    if repo.get("fork"):
        meta.append("fork")
    if repo.get("stargazers_count"):
        meta.append(f"★{repo['stargazers_count']}")
    tail = f" {' · '.join(meta)}" if meta else ""
    return f"| **[{name}]({url})** | {desc}{tail} |"


def build_table() -> str | None:
    try:
        repos = _repos()
    except Exception as exc:
        print(f"warning: could not fetch repos ({exc}); leaving README unchanged",
              file=sys.stderr)
        return None
    repos = [r for r in repos
             if not r.get("archived") and r.get("name", "").lower() not in HIDE]
    # flagship (most stars, then most recent) first; the rest stay pushed-sorted
    repos.sort(key=lambda r: (-(r.get("stargazers_count", 0))))
    lines = [
        "<!-- This table is auto-generated from GitHub by scripts/update_readme.py. -->",
        "| Project | What it is |",
        "| --- | --- |",
        *[_row(r) for r in repos],
        *[f"| {n} | {d} |" for n, d in PINNED_EXTRA],
    ]
    return "\n".join(lines)


def main(path: str) -> int:
    table = build_table()
    if table is None:
        return 0
    text = open(path, encoding="utf-8").read()
    if START not in text or END not in text:
        print(f"error: markers {START} / {END} not found in {path}", file=sys.stderr)
        return 1
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n{table}\n{END}",
        text,
        flags=re.DOTALL,
    )
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        print(f"updated {path}")
    else:
        print(f"{path} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "README.md"))
