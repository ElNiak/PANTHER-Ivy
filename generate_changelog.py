# tools/generate_changelog.py
"""Generate CHANGELOG.md from git history **without relying on git tags**."""

from __future__ import annotations
import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from git import Repo, Commit  # GitPython


# ---------- helpers ----------
CONVENTIONAL_RE = re.compile(r"^(?P<type>\w+)(?:\([\w\-]+\))?:\s+(?P<msg>.+)", re.I)
TYPES = ("feat", "fix", "docs", "refactor", "perf", "test", "chore", "other")


def parse_commit_message(message: str) -> Tuple[str, str]:
    """Return (type, text) using Conventional Commits, default 'other'."""
    m = CONVENTIONAL_RE.match(message.strip().splitlines()[0])
    if m:
        t = m.group("type").lower()
        return (t if t in TYPES else "other", m.group("msg"))
    return "other", message.strip()


def group_commits(commits: List[Commit]) -> Dict[str, Dict[str, List[str]]]:
    """Group commits {date: {type: [messages]}}."""
    buckets: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for c in commits:
        ctype, text = parse_commit_message(c.message)
        date_key = datetime.utcfromtimestamp(c.committed_date).strftime("%Y-%m-%d")
        buckets[date_key][ctype].append(text)
    return buckets


def render_markdown(buckets: Dict[str, Dict[str, List[str]]]) -> str:
    """Return Markdown changelog string newest-to-oldest."""
    lines: List[str] = ["# Changelog\n"]
    for date in sorted(buckets.keys(), reverse=True):
        lines.append(f"## {date}\n")
        for t in TYPES:
            if not buckets[date][t]:
                continue
            lines.append(f"### {t.capitalize()}\n")
            for msg in buckets[date][t]:
                lines.append(f"- {msg}")
            lines.append("")  # blank
    return "\n".join(lines).rstrip() + "\n"


# ---------- CLI ----------
def build(repo_path: Path, outfile: Path, include_merges: bool) -> None:
    repo = Repo(repo_path)
    commits = list(repo.iter_commits("HEAD"))
    if not include_merges:
        commits = [c for c in commits if len(c.parents) < 2]

    md = render_markdown(group_commits(commits))
    outfile.write_text(md, encoding="utf-8")
    print(f"Generated changelog → {outfile}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-generate CHANGELOG without tags.")
    ap.add_argument("--repo", default=".", type=Path, help="Path to git repo root")
    ap.add_argument("-o", "--output", default="CHANGELOG.md", type=Path)
    ap.add_argument(
        "--include-merges", action="store_true", help="Keep merge commits (default: ignore)"
    )
    args = ap.parse_args()
    build(args.repo.resolve(), args.output.resolve(), args.include_merges)


if __name__ == "__main__":  # pragma: no cover
    main()
