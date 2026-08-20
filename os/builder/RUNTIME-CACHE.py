#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "os" / "local"
CACHE = LOCAL / "build-cache" / "runtime"
BYPASS_ONCE = LOCAL / "runtime-cache-bypass.once"


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _assert_cache_path(path: Path) -> Path:
    local = _resolved(LOCAL)
    expected = _resolved(CACHE)
    target = _resolved(path)
    if target != expected:
        raise RuntimeError(f"refusing cache operation on unexpected path: {target}")
    if local not in target.parents:
        raise RuntimeError(f"refusing cache operation outside local builder state: {target}")
    return target


def _tree_stats(root: Path) -> tuple[int, int]:
    files = 0
    total = 0
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                files += 1
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
    return files, total


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024.0 or unit == "GiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{value} B"


def component_entries(component: str) -> list[dict]:
    root = CACHE / component
    out: list[dict] = []
    if not root.is_dir():
        return out
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        manifest = entry / "manifest.json"
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            doc = {}
        binary_name = "MMDVM-Host" if component == "mmdvm-host" else "DMRGateway"
        binary = entry / binary_name
        out.append({
            "key": entry.name,
            "binary": binary.is_file(),
            "binary_bytes": binary.stat().st_size if binary.is_file() else 0,
            "manifest": bool(doc),
            "built_at": doc.get("built_at"),
            "signature": doc.get("signature"),
        })
    return out


def status() -> int:
    cache = _assert_cache_path(CACHE)
    files, total = _tree_stats(cache)
    print("RUNTIME COMPILE CACHE")
    print("---------------------")
    print(f"Path:                  {cache}")
    print(f"Size:                  {_human_bytes(total)}")
    print(f"Files:                 {files}")
    print(f"Bypass next build:     {'yes' if BYPASS_ONCE.exists() else 'no'}")
    for component, label in (("mmdvm-host", "MMDVM-Host"), ("dmrgateway", "DMRGateway")):
        entries = component_entries(component)
        validish = sum(1 for e in entries if e["binary"] and e["manifest"])
        print(f"{label + ' entries:':22} {len(entries)} ({validish} with binary+manifest)")
        for entry in entries[-3:]:
            suffix = "ready" if entry["binary"] and entry["manifest"] else "incomplete"
            print(f"  {entry['key'][:16]}  {_human_bytes(int(entry['binary_bytes'])):>10}  {suffix}")
    return 0


def clear(confirm: str) -> int:
    if confirm != "CLEAR-CACHE":
        raise RuntimeError("cache clear requires exact confirmation CLEAR-CACHE")
    cache = _assert_cache_path(CACHE)
    if cache.exists():
        if cache.is_symlink():
            raise RuntimeError("refusing to clear symlinked runtime cache")
        shutil.rmtree(cache)
    cache.mkdir(parents=True, mode=0o700)
    os.chmod(cache, 0o700)
    print(f"Cleared runtime compile cache: {cache}")
    return 0


def bypass_next() -> int:
    LOCAL.mkdir(parents=True, exist_ok=True)
    os.chmod(LOCAL, 0o700)
    tmp = BYPASS_ONCE.with_suffix(".once.tmp")
    tmp.write_text("bypass once\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, BYPASS_ONCE)
    print("Next image build will ignore cached runtime binaries once.")
    return 0


def cancel_bypass() -> int:
    BYPASS_ONCE.unlink(missing_ok=True)
    print("Runtime cache bypass cancelled; normal cache reuse is enabled.")
    return 0


def consume_bypass() -> int:
    enabled = BYPASS_ONCE.exists()
    BYPASS_ONCE.unlink(missing_ok=True)
    print("1" if enabled else "0")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="YWD-Hotspot OS runtime compile cache helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    clear_p = sub.add_parser("clear")
    clear_p.add_argument("confirmation")
    sub.add_parser("bypass-next")
    sub.add_parser("cancel-bypass")
    sub.add_parser("consume-bypass")
    args = ap.parse_args()

    if args.cmd == "status":
        return status()
    if args.cmd == "clear":
        return clear(args.confirmation)
    if args.cmd == "bypass-next":
        return bypass_next()
    if args.cmd == "cancel-bypass":
        return cancel_bypass()
    return consume_bypass()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
