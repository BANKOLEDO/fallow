"""Step 4: propose clean filenames for top archive candidates using a local Gemma via Ollama.

This script NEVER renames anything. It only writes proposals to a CSV.
"""
import argparse
import csv
import json
import re
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd
import requests

OLLAMA = "http://localhost:11434"
CHECK_TIMEOUT_S = 10   # reachability check
GEN_TIMEOUT_S = 60     # one generation; local model, first call may include model load


BOILERPLATE = {
    "a_clean_human_readable_snake_case_filename_stem",
    "clean_human_readable_snake_case_filename",
    "human_readable_snake_case_filename",
    "file",
}


def snake(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:60] or "file"


def _looks_valid(stem: str, ext: str) -> bool:
    if not stem or stem in BOILERPLATE:
        return False
    low = stem.lower()
    if any(bad in low for bad in ("human_readable", "one_line", "under_90", "what_the_file")):
        return False
    if stem == snake(ext):
        return False
    return True


def ask(model: str, name: str, ext: str, size_bytes, age_days) -> dict:
    prompt = (
        "You rename messy files. Reply with a single JSON object and nothing else.\n"
        'Keys: "new_name" (snake_case stem, no extension) and "description" (one short line).\n'
        "Examples:\n"
        '{"new_name": "invoice_2023_q4", "description": "Q4 2023 billing invoice"}\n'
        '{"new_name": "family_vacation_2022_photo", "description": "Holiday photo from 2022"}\n'
        f"Now rename this file: {name} ({size_bytes} bytes, last opened {float(age_days):.0f} days ago)"
    )
    r = requests.post(
        f"{OLLAMA}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "format": "json",
              "options": {"temperature": 0.2}},
        timeout=GEN_TIMEOUT_S,
    )
    r.raise_for_status()
    try:
        data = json.loads(r.json().get("response", "{}"))
    except (ValueError, json.JSONDecodeError, AttributeError):
        data = {}
    stem = snake(str(data.get("new_name", "")))
    stem = re.sub(rf"_{re.escape(ext)}$", "", stem) if ext else stem
    if not _looks_valid(stem, ext):
        stem = snake(name.rsplit(".", 1)[0]) if "." in name else snake(name)
    desc = " ".join(str(data.get("description", "")).split())[:90]
    return {"stem": stem, "description": desc}


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 4: propose renames (never applies them).")
    ap.add_argument("--file", default="fallow_predictions.csv")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--model", default="gemma3:270m")
    ap.add_argument("--out", default="fallow_renames.csv")
    args = ap.parse_args()

    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=CHECK_TIMEOUT_S)
        tags.raise_for_status()
        have = [m.get("name", "") for m in tags.json().get("models", [])]
    except Exception:  # noqa: BLE001
        print("[SKIP] Ollama not reachable")
        return 0
    want = {args.model, args.model + ":latest"}
    if not any(h in want for h in have):
        print(f"[SKIP] model {args.model} not pulled in Ollama (run: ollama pull {args.model})")
        return 0

    try:
        df = pd.read_csv(args.file, keep_default_na=False)
    except FileNotFoundError:
        print(f"[ERROR] {args.file} not found. Run fallow.classify first.")
        return 1
    cand = df[df["pred_label"] == 1].sort_values("confidence_archive", ascending=False).head(args.limit)
    print(f"Asking {args.model} about {len(cand)} archive candidates (nothing will be renamed) ...")

    out = []
    for n, (_, row) in enumerate(cand.iterrows(), 1):
        name, ext = row["name"], str(row["ext"])
        print(f"  [{n}/{len(cand)}] {name}", flush=True)
        try:
            res = ask(args.model, name, ext, row["size_bytes"], row["age_days"])
            new = res["stem"] + (f".{ext}" if ext else "")
            desc = res["description"]
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] {name}: {type(e).__name__}: {str(e)[:120]}; keeping original name")
            new, desc = name, ""
        out.append({"path": row["path"], "old_name": name, "new_name": new, "description": desc})

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "old_name", "new_name", "description"])
        w.writeheader()
        w.writerows(out)

    if out:
        w1 = min(34, max(len(o["old_name"]) for o in out) + 1)
        w2 = min(40, max(len(o["new_name"]) for o in out) + 1)
        print(f"\n{'old_name':<{w1}}| {'new_name':<{w2}}| description")
        for o in out:
            print(f"{o['old_name'][:w1 - 1]:<{w1}}| {o['new_name'][:w2 - 1]:<{w2}}| {o['description']}")
    print(f"\nProposals written to {args.out}. No files were renamed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
