"""Step 1: walk a directory and emit one CSV row per file (label left empty)."""
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "venv"}
MAX_SIZE = 2 * 1024**3   # 2 GB
MAX_FILES = 2000
COLUMNS = [
    "path", "name", "ext", "size_bytes", "age_days", "mtime_days",
    "is_hidden", "parent_folder", "depth", "name_len",
    "has_number_in_name", "label",
]


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def collect(root: Path):
    now = time.time()
    records, scanned, skipped = [], 0, 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: print(f"[WARN] cannot read {e.filename}: {e.strerror}")):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            scanned += 1
            if scanned % 500 == 0:
                print(f"  ...scanned {scanned} files", flush=True)
            full = Path(dirpath) / fname
            try:
                if full.is_symlink():
                    skipped += 1
                    continue
                st = full.stat()
            except OSError as e:
                print(f"[WARN] skipping {full}: {e.strerror}")
                skipped += 1
                continue
            if st.st_size > MAX_SIZE:
                skipped += 1
                continue
            rel = full.relative_to(root)
            stem, ext = os.path.splitext(fname)
            records.append({
                "path": str(full),
                "name": fname,
                "ext": ext.lstrip(".").lower(),
                "size_bytes": st.st_size,
                "age_days": round(max(0.0, now - st.st_atime) / 86400, 2),
                "mtime_days": round(max(0.0, now - st.st_mtime) / 86400, 2),
                "is_hidden": int(any(p.startswith(".") for p in rel.parts)),
                "parent_folder": full.parent.name,
                "depth": len(rel.parts) - 1,
                "name_len": len(fname),
                "has_number_in_name": int(bool(re.search(r"\d", fname))),
                "label": "",
                "_mtime": st.st_mtime,
            })
    return records, scanned, skipped


def existing_labels(path) -> int:
    """How many labelled rows an existing CSV already holds (0 if missing or unreadable)."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return sum(1 for r in csv.DictReader(f) if (r.get("label") or "").strip())
    except (OSError, csv.Error):
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 1: collect file metadata.")
    ap.add_argument("--dir", default="~/Downloads", help="directory to scan")
    ap.add_argument("--out", default="fallow_data.csv", help="output CSV")
    ap.add_argument("--force", action="store_true", help="overwrite --out even if it holds labels")
    args = ap.parse_args()

    n_labels = existing_labels(args.out)
    if n_labels and not args.force:
        print(f"[ERROR] {args.out} already holds {n_labels} labels and collecting again would erase them.")
        print("        Use a different --out, or pass --force to overwrite.")
        return 1

    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        print(f"[ERROR] not a directory: {root}")
        return 1

    print(f"Scanning {root} ...", flush=True)
    records, scanned, skipped = collect(root)

    records.sort(key=lambda r: r["_mtime"], reverse=True)  # newest first
    capped = len(records) > MAX_FILES
    records = records[:MAX_FILES]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    total = sum(r["size_bytes"] for r in records)
    print(f"Total files scanned: {scanned} (skipped: {skipped})")
    print(f"Files written:       {len(records)}" + (f" (capped at {MAX_FILES}, newest first)" if capped else ""))
    print(f"Total size:          {human(total)}")
    print(f"Output:              {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
