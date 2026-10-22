"""Step 2: interactive labelling. Every label is written to disk immediately."""
import argparse
import csv
import os
import sys
import tempfile

KEYS = {"1": "1", "2": "2", "3": "3"}
NAMES = {"1": "archive", "2": "keep", "3": "delete"}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write_rows(path, fields, rows):
    """Crash-safe rewrite: write a temp file next to the CSV, then atomically replace."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def getkey() -> str:
    """Read a single keypress; fall back to line input when not a real terminal."""
    if sys.stdin.isatty():
        try:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            if ch == "\x03":
                raise KeyboardInterrupt
            return ch.lower()
        except ImportError:  # Windows
            try:
                import msvcrt
                return msvcrt.getwch().lower()
            except ImportError:
                pass
    line = sys.stdin.readline()
    if line == "":
        return "q"  # EOF
    return line.strip().lower()[:1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 2: label files by hand.")
    ap.add_argument("--file", default="fallow_data.csv")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"[ERROR] {args.file} not found. Run: python -m fallow.collect first.")
        return 1

    fields, rows = read_rows(args.file)
    labelled = sum(1 for r in rows if r["label"].strip())
    todo = [i for i, r in enumerate(rows) if not r["label"].strip()]
    print(f"{len(rows)} rows, {labelled} already labelled, {len(todo)} to go.")
    print("Keys: 1=archive  2=keep  3=delete  s=skip  q=quit\n")

    session = 0
    reached_200 = labelled >= 200
    try:
        for i in todo:
            r = rows[i]
            print(f"[{i}] {r['name']}  | ext={r['ext'] or '-'}  size={human(float(r['size_bytes']))}  age={r['age_days']}d")
            print("    > ", end="", flush=True)
            while True:
                k = getkey()
                if k in KEYS or k in ("s", "q"):
                    break
            if k == "q":
                print("quit")
                break
            if k == "s":
                print("skip")
                continue
            print(NAMES[k])
            rows[i]["label"] = KEYS[k]
            write_rows(args.file, fields, rows)  # saved before anything else happens
            labelled += 1
            session += 1
            if session % 25 == 0:
                print(f"--- {labelled} labelled in total ({session} this session) ---")
            if labelled >= 200 and not reached_200:
                reached_200 = True
                print("200 labels reached — you can stop here and still get a valid model.")
    except KeyboardInterrupt:
        print("\ninterrupted — all labels so far are already saved.")

    counts = {k: sum(1 for r in rows if r["label"] == k) for k in KEYS}
    print(f"\nSaved. Total labelled: {labelled}  (archive={counts['1']}, keep={counts['2']}, delete={counts['3']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
