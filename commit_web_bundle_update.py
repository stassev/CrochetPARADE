#!/usr/bin/env python3

"""
commit_web_bundle_update.py

Stages and commits the versioned JS/WASM bundle update produced by
`update_web_bundle.py`.

This script is intentionally conservative:
  - It validates that all required versioned assets exist at ONE common version.
  - It validates that all root .js/.html references point to that same version.
  - It stages only the expected files (avoids accidentally adding STLs/OBJs/etc).

Usage: run from repo root (no arguments).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

VERSIONED_PREFIXES_JS = [
    "bezier",
    "mesh",
    "parse",
    "simplify",
    "sphere-generator",
    "transform_controls",
]

COMPILED_PREFIXES = [
    "graph",
    "periphery",
]

ALL_PREFIXES = tuple(VERSIONED_PREFIXES_JS + COMPILED_PREFIXES)

VERSIONED_ASSET_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<prefix>"
    + "|".join(re.escape(p) for p in ALL_PREFIXES)
    + r")(?P<ver>\d+)\.(?P<ext>js|wasm)(?![A-Za-z0-9_-])"
)


def die(msg: str, code: int = 2) -> "None":
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def run(argv: list[str]) -> str:
    p = subprocess.run(argv, cwd=ROOT, check=True, text=True, capture_output=True)
    return p.stdout


def find_versions(prefix: str, ext: str) -> list[int]:
    rx = re.compile(rf"^{re.escape(prefix)}(\d+)\.{re.escape(ext)}$")
    out: list[int] = []
    for p in ROOT.iterdir():
        if not p.is_file():
            continue
        m = rx.match(p.name)
        if not m:
            continue
        out.append(int(m.group(1)))
    out.sort()
    return out


def main() -> int:
    # 1) Determine a common version by inspecting the files on disk.
    required: dict[tuple[str, str], int] = {}

    for pref in VERSIONED_PREFIXES_JS:
        vs = find_versions(pref, "js")
        if len(vs) != 1:
            die(f"Expected exactly one {pref}<N>.js, found: {vs}")
        required[(pref, "js")] = vs[0]

    for pref in COMPILED_PREFIXES:
        vjs = find_versions(pref, "js")
        vws = find_versions(pref, "wasm")
        if len(vjs) != 1 or len(vws) != 1:
            die(f"Expected exactly one {pref}<N>.js and {pref}<N>.wasm, found: js={vjs}, wasm={vws}")
        if vjs[0] != vws[0]:
            die(f"Mismatched {pref} versions: js={vjs[0]} wasm={vws[0]}")
        required[(pref, "js")] = vjs[0]
        required[(pref, "wasm")] = vws[0]

    versions = sorted({v for v in required.values()})
    if len(versions) != 1:
        die(f"Bundle versions are not consistent across assets: {required}")
    ver = versions[0]
    print(f"Detected bundle version: {ver}")

    # 2) Validate key references.
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    must_in_index = [
        f"bezier{ver}.js",
        f"parse{ver}.js",
        f"simplify{ver}.js",
        f"sphere-generator{ver}.js",
        f"graph{ver}.js",
        f"mesh{ver}.js",
    ]
    for needle in must_in_index:
        if needle not in index:
            die(f"index.html does not reference {needle}")

    mesh = (ROOT / f"mesh{ver}.js").read_text(encoding="utf-8")
    if f"transform_controls{ver}.js" not in mesh:
        die(f"mesh{ver}.js does not reference transform_controls{ver}.js")

    worker = (ROOT / "periphery_worker.js").read_text(encoding="utf-8")
    if f"importScripts('periphery{ver}.js')" not in worker:
        die(f"periphery_worker.js does not importScripts('periphery{ver}.js')")

    # 3) Ensure no mixed-version references remain in root .js/.html.
    text_paths = [p for p in ROOT.iterdir() if p.is_file() and p.suffix in (".js", ".html")]
    bad: list[tuple[str, str]] = []
    for p in sorted(text_paths, key=lambda x: x.name):
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in VERSIONED_ASSET_RE.finditer(txt):
            if int(m.group("ver")) != ver:
                bad.append((p.name, m.group(0)))
    if bad:
        lines = "\n".join(f"  {fn}: {ref}" for fn, ref in bad[:50])
        die(f"Found stale/mixed versioned references:\n{lines}")

    # 4) Stage only expected changes.
    # First: stage tracked modifications/deletions (but not new files).
    run(["git", "add", "-u"])

    # Then: add the new versioned assets and scripts.
    to_add = [
        "index.html",
        "periphery_wasm.js",
        "periphery_worker.js",
        "update_web_bundle.py",
        "commit_web_bundle_update.py",
    ]
    for pref in VERSIONED_PREFIXES_JS:
        to_add.append(f"{pref}{ver}.js")
    for pref in COMPILED_PREFIXES:
        to_add.append(f"{pref}{ver}.js")
        to_add.append(f"{pref}{ver}.wasm")

    # Validate all to_add exist before staging (prevents committing accidental deletions).
    missing = [name for name in to_add if not (ROOT / name).exists()]
    if missing:
        die("Refusing to stage: missing expected files:\n  " + "\n  ".join(missing))

    run(["git", "add", "--"] + to_add)

    # 5) Sanity check staged paths (avoid accidentally committing unrelated untracked files).
    staged = run(["git", "diff", "--cached", "--name-status"]).splitlines()

    def is_allowed(path: str) -> bool:
        if path in ("index.html", "periphery_wasm.js", "periphery_worker.js", "update_web_bundle.py", "commit_web_bundle_update.py"):
            return True
        return bool(re.match(rf"^({'|'.join(re.escape(p) for p in ALL_PREFIXES)})\d+\.(js|wasm)$", path))

    bad_paths: list[str] = []
    for line in staged:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()
        paths = [p.strip() for p in parts[1:] if p.strip()]
        # Renames/copies are reported as: Rxxx <old> <new> (two paths).
        # Everything else is: <status> <path>.
        for path in paths:
            if not is_allowed(path):
                bad_paths.append(line)
                break
    if bad_paths:
        die("Refusing to commit: unexpected staged paths:\n" + "\n".join(bad_paths))

    # 6) Commit.
    msg = f"Bump web bundle to v{ver}"
    print("+ git commit -m", msg)
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)

    print("Committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
