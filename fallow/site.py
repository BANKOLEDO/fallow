"""Build the static site from your real run: python -m fallow.site

Reads fallow_predictions.csv (and fallow_renames.csv if present) and writes site/index.html.
Plain HTML and CSS, no JavaScript, no build step. File names are HTML-escaped.
"""
import argparse
import csv
import html
import math
import sys
from pathlib import Path

import pandas as pd

from fallow.report import build_report

COLS = 25
MAX_CELLS = 400
TEMPLATE = Path(__file__).with_name("site_template.html")
CLASS_OF = {1: "a", 2: "k", 3: "d"}  # archive, keep, delete
# Parcel seeds on a 25x16 reference grid; scaled to the real grid height.
BASE_SEEDS = {
    "k": [(3, 4), (8, 12), (13, 2), (19, 13), (22, 3), (0, 14)],
    "a": [(10, 7), (16, 7), (5, 14), (22, 9), (7, 1)],
    "d": [(23, 15), (1, 0), (14, 15), (18, 1)],
}


def allocate(counts: dict, total_cells: int) -> dict:
    """Cells per class. One cell per file when it fits, otherwise proportional."""
    n = sum(counts.values())
    if n <= total_cells:
        return dict(counts)
    raw = {k: v * total_cells / n for k, v in counts.items()}
    cells = {k: int(raw[k]) for k in raw}
    for k in sorted(raw, key=lambda k: raw[k] - cells[k], reverse=True)[: total_cells - sum(cells.values())]:
        cells[k] += 1
    for k in cells:  # a class that exists never vanishes from the map
        if counts[k] > 0 and cells[k] == 0:
            donor = max(cells, key=cells.get)
            cells[donor] -= 1
            cells[k] = 1
    return cells


def layout(cells: dict) -> list:
    """Assign a class to every cell, grouped into contiguous parcels. Returns row-major list."""
    total = sum(cells.values())
    rows = max(1, math.ceil(total / COLS))
    sy = (rows - 1) / 15 if rows > 1 else 0.0
    seeds = {k: [(x, y * sy) for x, y in pts] for k, pts in BASE_SEEDS.items()}
    pos = [(i % COLS, i // COLS) for i in range(total)]

    def dist(p, k):
        return min((p[0] - x) ** 2 + (p[1] - y) ** 2 for x, y in seeds[k])

    grid = {p: min(seeds, key=lambda k: dist(p, k)) for p in pos}
    have = {k: sum(1 for v in grid.values() if v == k) for k in seeds}
    while have != cells:
        over = [k for k in seeds if have[k] > cells.get(k, 0)]
        under = [k for k in seeds if have[k] < cells.get(k, 0)]
        best = None
        for p, k in grid.items():
            if k in over:
                for u in under:
                    delta = dist(p, u) - dist(p, k)
                    if best is None or delta < best[0]:
                        best = (delta, p, k, u)
        _, p, k, u = best
        grid[p] = u
        have[k] -= 1
        have[u] += 1
    return [grid[p] for p in pos]


def renames_section(path: Path) -> str:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return ""
    rows = [r for r in rows if r.get("new_name")]
    if not rows:
        return ""
    e = html.escape
    body = "\n".join(
        f'        <tr><td class="old" data-label="Current name">{e(r["old_name"])}</td>'
        f'<td class="new" data-label="Suggested name">{e(r["new_name"])}</td>'
        f'<td data-label="What it is">{e(r.get("description", ""))}</td></tr>'
        for r in rows
    )
    return f"""  <section aria-labelledby="rename-title">
    <div class="head">
      <h2 id="rename-title">Suggested names for old files</h2>
      <p>Written by a small language model running on your computer. You choose whether to use any of them.</p>
    </div>
    <table>
      <thead><tr><th>Current name</th><th>Suggested name</th><th>What it is</th></tr></thead>
      <tbody>
{body}
      </tbody>
    </table>
  </section>"""


def build_page(df: pd.DataFrame, renames_path: Path = None, redact: bool = False, note: str = "") -> str:
    df = df.copy()
    if redact:
        df["name"] = [f"file_{i + 1:04d}" + (f".{x}" if x else "") for i, x in enumerate(df["ext"].astype(str))]
    n = len(df)
    counts = {"k": 0, "a": 0, "d": 0}
    for v, k in CLASS_OF.items():
        counts[k] = int((df["pred_label"] == v).sum())

    cells = allocate(counts, MAX_CELLS)
    classes = layout(cells)
    grid = "".join(f'<i class="cell {c}"></i>' for c in classes)
    delay_css = "\n".join(
        f"  .cell:nth-child({COLS}n+{c + 1}) {{ animation-delay: {c * 24}ms; }}" for c in range(COLS)
    )
    caption = ("One square per file." if n <= MAX_CELLS
               else f"Each square stands for about {math.ceil(n / MAX_CELLS)} files.")

    lines = html.escape(build_report(df)).split("\n")
    lines[-1] = f'<span class="sum">{lines[-1]}</span>'

    out = TEMPLATE.read_text(encoding="utf-8")
    renames = "" if redact or renames_path is None else renames_section(renames_path)
    for token, value in {
        "@@DELAY_CSS@@": delay_css,
        "@@ARIA@@": f"Map of {n} files: {counts['k']} keep, {counts['a']} archive, {counts['d']} delete",
        "@@GRID@@": grid,
        "@@N_K@@": str(counts["k"]), "@@N_A@@": str(counts["a"]), "@@N_D@@": str(counts["d"]),
        "@@CAPTION@@": caption,
        "@@REPORT@@": "\n".join(lines),
        "@@RENAMES@@": renames,
        "@@NOTE@@": f'    <p class="demo">{html.escape(note)}</p>' if note else "",
    }.items():
        out = out.replace(token, value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow: build the static site from your real results.")
    ap.add_argument("--file", default="fallow_predictions.csv")
    ap.add_argument("--renames", default="fallow_renames.csv")
    ap.add_argument("--out", default="site/index.html")
    ap.add_argument("--redact", action="store_true",
                    help="replace real file names with file_0001.ext and omit the rename table")
    ap.add_argument("--note", default="", help="optional small notice shown under the map (e.g. 'Demo data')")
    args = ap.parse_args()

    try:
        df = pd.read_csv(args.file, keep_default_na=False)
    except FileNotFoundError:
        print(f"[ERROR] {args.file} not found. Run fallow.classify first.")
        return 1
    if df.empty:
        print("[ERROR] predictions file is empty.")
        return 1

    page = build_page(df, Path(args.renames), args.redact, args.note)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(page)} bytes) from {len(df)} files.")
    if args.redact:
        print("File names were replaced and the rename table was left out.")
    else:
        print("[NOTE] The page shows real file names from your folder. Review it, or use --redact, before publishing.")
    if not args.redact and not Path(args.renames).exists():
        print(f"[INFO] {args.renames} not found, so the rename table was left out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
