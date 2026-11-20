"""Optional, conservative integration with the existing From Lab to Code site.

Only edits docs/app.js and the root README.md in a *local checkout*. It neither
commits nor pushes nor fabricates an article or hosted demo URL.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import re
import sys

PROJECT_LINK = "https://github.com/Ertugrulmutlu/from-lab-to-code/tree/main/05-realtime-robot-control"
NEW_CARD = """  {
    id: '05', title: 'Real-Time Robot Control Lab',
    short: 'Network RTT · Blocking vs. async · Braking',
    category: 'Control',
    description: 'Compare blocking and non-blocking robot controllers under delayed telemetry and finite braking in a reproducible interactive simulation.',
    githubUrl: '""" + PROJECT_LINK + """',
    articleUrl: '',
    status: 'published', featured: false, icon: 'gauge', accent: 'teal',
    previewSteps: ['Network Delay', 'Speed Estimation', 'Braking Distance', 'Controller Comparison']
  },"""
NEW_ROW = "| 05 | [Real-Time Robot Control Lab](05-realtime-robot-control/) | Virtual network delay, blocking vs. non-blocking sensing, braking physics, deterministic replay |"


def update_card(source: str) -> str:
    if re.search(r"id:\s*'05',\s*title:\s*'Real-Time Robot Control Lab'", source):
        return source  # already updated
    old = re.compile(r"(?m)^[ \t]*\{id:'05',title:'Control Basics'[^\n]*\},[ \t]*$")
    result, count = old.subn(lambda _match: NEW_CARD, source)
    if count != 1:
        raise ValueError("Expected exactly one Project #05 'Control Basics' placeholder in docs/app.js")
    return result


def update_readme(source: str) -> str:
    if re.search(r"(?m)^\| 05 \| \[Real-Time Robot Control Lab\]", source):
        return source
    old = re.compile(r"(?m)^(\| 04 \|[^\n]*\|)[ \t]*$")
    updated, count = old.subn(lambda m: m.group(1) + "\n" + NEW_ROW, source)
    if count != 1:
        raise ValueError("Expected exactly one Project #04 row in root README.md")
    return updated


def integrate(root: Path, dry_run: bool = False) -> list[str]:
    root = root.resolve()
    project = root / '05-realtime-robot-control'
    js_path = root / 'docs' / 'app.js'
    readme_path = root / 'README.md'
    if not project.is_dir():
        raise ValueError(f"Expected copied Project #05 folder at {project}")
    if not js_path.is_file() or not readme_path.is_file():
        raise ValueError(f"Expected existing docs/app.js and README.md in repository root {root}")

    changes = {}
    for path, operation in ((js_path, update_card), (readme_path, update_readme)):
        before = path.read_text(encoding='utf-8')
        after = operation(before)
        changes[path] = (before, after)

    messages = []
    for path, (before, after) in changes.items():
        label = str(path.relative_to(root))
        if before == after:
            messages.append(f"UNCHANGED {label}")
            continue
        if dry_run:
            diff = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile=f'a/{label}', tofile=f'b/{label}')
            messages.append(''.join(diff).rstrip())
        else:
            path.write_text(after, encoding='utf-8')
            messages.append(f"UPDATED {label}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description='Integrate Project #05 as a local site card and README entry')
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2],
                        help='Path to the existing from-lab-to-code repository root')
    parser.add_argument('--dry-run', action='store_true', help='Print local diffs without modifying files')
    args = parser.parse_args()
    try:
        print('\n\n'.join(integrate(args.repo_root, dry_run=args.dry_run)))
    except (ValueError, OSError) as exc:
        print(f'Cannot update showcase: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
