"""Step 6 (optional): three-sentence plain-English summary via Paper Instruments Ultramarine.

Skips cleanly when ULTRAMARINE_API_KEY is not set. What is sent is the Step 5 report text:
counts, a size total, and the names (not full paths) of the 10 oldest archive candidates.
"""
import argparse
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd

from fallow import tracing
from fallow.report import build_report

DEFAULT_BASE_URL = "https://api.paperinstruments.com/v1"
DEFAULT_MODEL = "ultramarine-1-flash"
# Paper Instruments list prices (Oct 2026), USD per million tokens. Estimate only.
PRICE_IN, PRICE_CACHED, PRICE_OUT = 0.15, 0.03, 0.50
PROMPT = ("Write three short sentences summarising this file-triage report for a "
          "non-technical reader. Be concrete. Use the numbers provided.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 6: optional prose summary.")
    ap.add_argument("--file", default="fallow_predictions.csv")
    ap.add_argument("--out", default="fallow_report.md")
    args = ap.parse_args()

    key = os.environ.get("ULTRAMARINE_API_KEY", "").strip()
    if not key:
        print("[SKIP] ULTRAMARINE_API_KEY not set")
        return 0

    try:
        df = pd.read_csv(args.file, keep_default_na=False)
    except FileNotFoundError:
        print(f"[ERROR] {args.file} not found. Run fallow.classify first.")
        return 1
    report = build_report(df)

    base_url = os.environ.get("ULTRAMARINE_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("ULTRAMARINE_MODEL", DEFAULT_MODEL)
    tracing.init()
    print(f"Calling {model} at {base_url} ...", flush=True)
    try:
        from openai import OpenAI, Timeout
        client = OpenAI(base_url=base_url, api_key=key, max_retries=0,
                        timeout=Timeout(60.0, connect=10.0))
        with tracing.span("fallow.prose"):
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"{PROMPT}\n\n{report}"}],
                max_completion_tokens=2000,
            )
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] prose call failed, continuing without it: {type(e).__name__}: {str(e)[:200]}")
        return 0

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        print("[WARN] model returned empty text.")
        return 0
    print("\n" + text + "\n")

    u = resp.usage
    if u is not None:
        pin, pout = u.prompt_tokens or 0, u.completion_tokens or 0
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        cost = ((pin - cached) * PRICE_IN + cached * PRICE_CACHED + pout * PRICE_OUT) / 1_000_000
        print(f"tokens: {pin} in ({cached} cached) + {pout} out = {pin + pout}")
        print(f"estimated cost: ${cost:.6f} (at {DEFAULT_MODEL} list prices)")
    else:
        print("[WARN] API returned no usage data; token count and cost unavailable.")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# Fallow report\n\n" + text + "\n")
    print(f"Saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
