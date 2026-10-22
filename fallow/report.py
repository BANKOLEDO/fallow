"""Step 5: plain-text summary of the predictions. Clean enough to quote verbatim."""
import argparse
import sys

import pandas as pd

GB = 1024 ** 3
LABELS = {1: "archive", 2: "keep", 3: "delete"}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def build_report(df: pd.DataFrame) -> str:
    total = len(df)
    counts = {k: int((df["pred_label"] == k).sum()) for k in LABELS}
    reclaim = float(df.loc[df["pred_label"] == 3, "size_bytes"].astype(float).sum()) / GB

    lines = ["FALLOW REPORT", "=============", f"Files analysed: {total}", ""]
    lines.append("Predicted action:")
    for k, name in LABELS.items():
        lines.append(f"  {name:<8}{counts[k]:>6}")
    lines += ["", f"Reclaimable space (predicted delete): {reclaim:.2f} GB", ""]

    old = df[df["pred_label"] == 1].copy()
    old["age_days"] = old["age_days"].astype(float)
    old = old.sort_values("age_days", ascending=False).head(10)
    lines.append("10 oldest archive candidates:")
    if old.empty:
        lines.append("  (none)")
    for i, (_, r) in enumerate(old.iterrows(), 1):
        lines.append(f"  {i:>2}. {r['name']}  ({r['age_days']:.0f} days, {human(float(r['size_bytes']))})")
    lines += ["", f"Fallow triaged {total} files and found {reclaim:.2f} GB that can likely be deleted."]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 5: print a plain-text report.")
    ap.add_argument("--file", default="fallow_predictions.csv")
    args = ap.parse_args()
    try:
        df = pd.read_csv(args.file, keep_default_na=False)
    except FileNotFoundError:
        print(f"[ERROR] {args.file} not found. Run fallow.classify first.")
        return 1
    if df.empty:
        print("[ERROR] predictions file is empty.")
        return 1
    print(build_report(df))
    return 0


if __name__ == "__main__":
    sys.exit(main())
