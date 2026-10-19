"""Check that every link in the repository resolves: relative links to files that exist,
and absolute links to pages that answer 200.

    python scripts/check_links.py            # relative and absolute
    python scripts/check_links.py --offline  # relative only
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def markdown_files() -> list[Path]:
    skip = {".venv", ".terraform"}  # installed packages and providers, not ours
    return sorted(p for p in ROOT.rglob("*.md") if not skip & set(p.parts))


def links() -> tuple[list[tuple[Path, str]], set[str]]:
    relative, absolute = [], set()
    for path in markdown_files():
        for target in LINK.findall(path.read_text()):
            if target.startswith(("http://", "https://")):
                absolute.add(target.split("#")[0])
            elif not target.startswith(("#", "mailto:")):
                relative.append((path, target.split("#")[0]))
    evidence = yaml.safe_load((ROOT / "evidence" / "evidence.yml").read_text())
    for e in evidence.values():
        absolute.add(f"https://github.com/technobasant/{e['repo']}/blob/main/{e['file']}")
    return relative, absolute


TRANSIENT = {429, 500, 502, 503, 504}


def fetch(url: str, attempts: int = 4) -> tuple[str, int | str]:
    """GET a URL; retry rate limits, server errors and timeouts with backoff. A 404 is final."""
    result: int | str = "not tried"
    for attempt in range(attempts):
        try:
            r = httpx.get(url, follow_redirects=True, timeout=30, headers={"User-Agent": "link-check"})
            result = r.status_code
            if result not in TRANSIENT:
                return url, result
        except httpx.HTTPError as exc:
            result = type(exc).__name__
        time.sleep(2**attempt)
    return url, result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    relative, absolute = links()
    broken = [f"{p.relative_to(ROOT)} -> {t}" for p, t in relative if t and not (p.parent / t).exists()]
    if not args.offline:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for url, status in pool.map(fetch, sorted(absolute)):
                if status != 200:
                    broken.append(f"{url} -> {status}")
    checked = len(relative) + (0 if args.offline else len(absolute))
    if broken:
        sys.exit("broken links:\n  " + "\n  ".join(broken))
    print(f"{checked} links ok")


if __name__ == "__main__":
    main()
