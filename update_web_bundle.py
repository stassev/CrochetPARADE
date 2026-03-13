#!/usr/bin/env python3

"""
update_web_bundle.py

Builds the Emscripten WASM bundles (graph + periphery) and bumps the numeric
suffix on all versioned JS/WASM assets so browsers will re-download updated
files.

Default behavior (no arguments):
  - Detect current max version among versioned assets.
  - Increment it (e.g. 59 -> 60).
  - Compile:
      graph.cpp    -> graph<NEW>.js + graph<NEW>.wasm
      periphery.cpp-> periphery<NEW>.js + periphery<NEW>.wasm
  - Rename:
      parse<OLD>.js, mesh<OLD>.js, bezier<OLD>.js, simplify<OLD>.js,
      transform_controls<OLD>.js, sphere-generator<OLD>.js
    to the new version.
  - Update references/imports in tracked .js/.html/.py files.
  - Delete older graph/periphery numbered bundles not matching NEW.

Use --dry-run to print actions without changing files.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEXT_REF_EXTS = frozenset({".js", ".html", ".py"})
SKIP_DIR_NAMES = frozenset({".git", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"})

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

ALL_VERSIONED_PREFIXES = tuple(VERSIONED_PREFIXES_JS + COMPILED_PREFIXES)

VERSIONED_ASSET_RE = re.compile(
    r"^(?P<prefix>"
    + "|".join(re.escape(p) for p in ALL_VERSIONED_PREFIXES)
    + r")(?P<ver>\d+)\.(?P<ext>js|wasm)$"
)

# Same as VERSIONED_ASSET_RE, but matches references inside text files.
VERSIONED_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<prefix>"
    + "|".join(re.escape(p) for p in ALL_VERSIONED_PREFIXES)
    + r")(?P<ver>\d+)\.(?P<ext>js|wasm)(?![A-Za-z0-9_-])"
)


@dataclass(frozen=True)
class Rename:
    src: Path
    dst: Path


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def shlex_join(argv: list[str]) -> str:
    # Minimal join helper (keeps script self-contained).
    out: list[str] = []
    for a in argv:
        if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", a):
            out.append(a)
        else:
            out.append("'" + a.replace("'", "'\"'\"'") + "'")
    return " ".join(out)


def detect_max_version() -> int:
    max_v: int | None = None
    for p in ROOT.iterdir():
        m = VERSIONED_ASSET_RE.match(p.name)
        if not m:
            continue
        try:
            v = int(m.group("ver"))
        except ValueError:
            continue
        max_v = v if max_v is None else max(max_v, v)
    # If nothing is versioned yet, default to 59 -> 60.
    return max_v if max_v is not None else 59


def find_highest_versioned(prefix: str, ext: str) -> tuple[int | None, Path | None]:
    best_v: int | None = None
    best_p: Path | None = None
    rx = re.compile(rf"^{re.escape(prefix)}(?P<ver>\d+)\.{re.escape(ext)}$")
    for p in ROOT.iterdir():
        if not p.is_file():
            continue
        m = rx.match(p.name)
        if not m:
            continue
        v = int(m.group("ver"))
        if best_v is None or v > best_v:
            best_v = v
            best_p = p
    return best_v, best_p


def run_cmd(argv: list[str], *, env: dict[str, str], dry_run: bool) -> None:
    print("+", shlex_join(argv))
    if dry_run:
        return
    subprocess.run(argv, cwd=ROOT, env=env, check=True)


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def iter_versioned_ref_text_paths() -> list[Path]:
    compiled_js_rx = re.compile(r"^(graph|periphery)\d+\.js$")
    paths: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in TEXT_REF_EXTS:
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if compiled_js_rx.match(p.name):
            continue
        paths.append(p)
    paths.sort(key=lambda p: p.relative_to(ROOT).as_posix())
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    ap.add_argument(
        "--force-version",
        type=int,
        default=None,
        help="Force the new bundle version (advanced). If omitted, uses max+1.",
    )
    args = ap.parse_args()

    current_max = detect_max_version()
    new_ver = int(args.force_version) if args.force_version is not None else (current_max + 1)

    if new_ver <= current_max:
        eprint(f"Refusing to use new_ver={new_ver} (current max is {current_max}).")
        return 2

    # Ensure we won't overwrite an existing bundle version.
    collision = []
    for pref in ALL_VERSIONED_PREFIXES:
        for ext in ("js", "wasm"):
            p = ROOT / f"{pref}{new_ver}.{ext}"
            if p.exists():
                collision.append(p.name)
    if collision:
        eprint("Refusing to overwrite existing files:", ", ".join(sorted(set(collision))))
        return 2

    print(f"Detected current max bundle version: {current_max}")
    print(f"New bundle version: {new_ver}")

    empp = Path("/usr/lib/emscripten/em++")
    if not empp.exists():
        eprint(f"Missing compiler: {empp}")
        return 2

    env = dict(os.environ)
    env.setdefault("EM_CACHE", "/tmp/emscripten_cache")
    if not args.dry_run:
        Path(env["EM_CACHE"]).mkdir(parents=True, exist_ok=True)

    # 1) Compile Emscripten outputs directly to the new versioned filenames.
    run_cmd(
        [
            str(empp),
            "-Wall",
            "graph.cpp",
            "-o",
            f"graph{new_ver}.js",
            "-O3",
            "-std=c++17",
            "-ffast-math",
            "-sEXPORTED_FUNCTIONS=_performLayout,_malloc,_free",
            "-sEXPORTED_RUNTIME_METHODS=ccall,UTF8ToString,stringToUTF8",
            "-sALLOW_MEMORY_GROWTH=1",
            "-sMAXIMUM_MEMORY=4GB",
        ],
        env=env,
        dry_run=args.dry_run,
    )
    run_cmd(
        [
            str(empp),
            "-Wall",
            "periphery.cpp",
            "-o",
            f"periphery{new_ver}.js",
            "-O3",
            "-std=c++17",
            "-sEXPORTED_FUNCTIONS=_find_periphery,_cancel_periphery,_malloc,_free",
            "-sEXPORTED_RUNTIME_METHODS=ccall,UTF8ToString,stringToUTF8,lengthBytesUTF8",
            "-sALLOW_MEMORY_GROWTH=1",
            "-sMAXIMUM_MEMORY=4GB",
            "-sINITIAL_MEMORY=536870912",
            "-sENVIRONMENT=web,worker",
        ],
        env=env,
        dry_run=args.dry_run,
    )

    # 2) Rename the numbered JS assets to the new version.
    renames: list[Rename] = []
    for pref in VERSIONED_PREFIXES_JS:
        old_v, old_p = find_highest_versioned(pref, "js")
        if old_p is None or old_v is None:
            eprint(f"Missing expected file: {pref}<N>.js (cannot bump).")
            return 2
        if old_v == new_ver:
            continue
        renames.append(Rename(src=old_p, dst=ROOT / f"{pref}{new_ver}.js"))

    # Sanity: ensure renames don't collide.
    dst_set = set()
    for r in renames:
        if r.dst in dst_set:
            eprint(f"Internal error: duplicate destination {r.dst}")
            return 2
        dst_set.add(r.dst)
        if r.dst.exists():
            eprint(f"Destination already exists: {r.dst.name}")
            return 2

    for r in renames:
        print(f"mv {r.src.name} -> {r.dst.name}")
        if not args.dry_run:
            r.src.replace(r.dst)

    # 3) Update references/imports across tracked JS/HTML/PY files
    #    (excluding compiled graph/periphery outputs).
    # Replace ANY versioned reference with the new version.
    def repl(m: re.Match[str]) -> str:
        pref = m.group("prefix")
        ext = m.group("ext")
        return f"{pref}{new_ver}.{ext}"

    touched: list[Path] = []
    for p in iter_versioned_ref_text_paths():
        rel = p.relative_to(ROOT).as_posix()
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_txt = VERSIONED_REF_RE.sub(repl, txt)
        if new_txt != txt:
            touched.append(p)
            print(f"edit {rel}")
            if not args.dry_run:
                atomic_write_text(p, new_txt)

    # 4) Delete older graph/periphery numbered bundles (js + wasm) not matching new_ver.
    keep = {
        f"graph{new_ver}.js",
        f"graph{new_ver}.wasm",
        f"periphery{new_ver}.js",
        f"periphery{new_ver}.wasm",
    }
    del_rx = re.compile(r"^(graph|periphery)\d+\.(js|wasm)$")
    for p in sorted(ROOT.iterdir(), key=lambda x: x.name):
        if not p.is_file():
            continue
        if not del_rx.match(p.name):
            continue
        if p.name in keep:
            continue
        print(f"rm {p.name}")
        if not args.dry_run:
            p.unlink()

    # 5) Validate: ensure touched JS/HTML/PY files don't refer to old bundle numbers.
    if not args.dry_run:
        bad: list[tuple[str, str]] = []
        for p in touched:
            txt = p.read_text(encoding="utf-8")
            for m in VERSIONED_REF_RE.finditer(txt):
                if int(m.group("ver")) != new_ver:
                    bad.append((p.relative_to(ROOT).as_posix(), m.group(0)))
        if bad:
            eprint("Found stale versioned references after update:")
            for fn, ref in bad[:50]:
                eprint(f"  {fn}: {ref}")
            return 2

        # Ensure the key assets exist.
        must_exist = [
            ROOT / f"{pref}{new_ver}.js" for pref in VERSIONED_PREFIXES_JS
        ] + [
            ROOT / f"graph{new_ver}.js",
            ROOT / f"graph{new_ver}.wasm",
            ROOT / f"periphery{new_ver}.js",
            ROOT / f"periphery{new_ver}.wasm",
        ]
        missing = [p.name for p in must_exist if not p.exists()]
        if missing:
            eprint("Missing expected output files:", ", ".join(missing))
            return 2

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
