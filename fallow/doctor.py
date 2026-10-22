"""Print a checklist of what will work on this machine: python -m fallow.doctor

It inspects installed packages, environment variables and localhost Ollama. It does not
call any paid or remote service, so it is free and safe to run anywhere. Paste its output
into your write-up.
"""
import argparse
import importlib
import os
import platform
import shutil
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OLLAMA = "http://localhost:11434"


def has(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception:  # noqa: BLE001
        return False


def row(status: str, name: str, detail: str) -> None:
    print(f"  [{status:<8}] {name}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow: check what is installed and configured.")
    ap.add_argument("--model", default="gemma3:270m")
    args = ap.parse_args()

    print("FALLOW DOCTOR")
    print("=============")
    py_ok = sys.version_info >= (3, 11)
    row("OK" if py_ok else "WARN", "Python", platform.python_version() + ("" if py_ok else " (3.11+ expected)"))

    core = ["pandas", "numpy", "sklearn", "requests", "dotenv"]
    missing = [m for m in core if not has(m)]
    if missing:
        row("MISSING", "Core packages", ", ".join(missing) + " (pip install pandas scikit-learn python-dotenv requests)")
    else:
        row("OK", "Core packages", "pandas, numpy, scikit-learn, requests, python-dotenv")

    print("\nClassifier (step 3):")
    local = has("tabpfn")
    row("OK" if local else "FALLBACK", "Local TabPFN",
        "installed (weights download on first fit and need an accepted license; not checked here)"
        if local else "not installed")
    key = bool(os.environ.get("TABPFN_API_KEY", "").strip())
    client = has("tabpfn_client")
    row("OK" if key and client else "SKIP", "TabPFN API",
        "key set and tabpfn-client installed" if key and client
        else "needs TABPFN_API_KEY" + ("" if client else " and pip install tabpfn-client"))
    expected = ("TabPFN (local), then API or random forest if it fails" if local
                else "TabPFN API" if key and client else "RandomForest fallback (NOT TabPFN)")
    row("INFO", "Expected classifier", expected)

    print("\nOptional steps:")
    try:
        import requests
        r = requests.get(f"{OLLAMA}/api/tags", timeout=10)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        if any(n in (args.model, args.model + ":latest") for n in names):
            row("OK", "Rename (step 4)", f"Ollama reachable, {args.model} available")
        else:
            row("SKIP", "Rename (step 4)", f"Ollama reachable but {args.model} not pulled (ollama pull {args.model})")
    except Exception:  # noqa: BLE001
        row("SKIP", "Rename (step 4)", "Ollama not reachable at localhost:11434")

    um = bool(os.environ.get("ULTRAMARINE_API_KEY", "").strip())
    row("OK" if um and has("openai") else "SKIP", "Prose (step 6)",
        "key set and openai installed" if um and has("openai")
        else "needs ULTRAMARINE_API_KEY" + ("" if has("openai") else " and pip install openai"))

    el = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
    player = "afplay" if platform.system() == "Darwin" and shutil.which("afplay") else next(
        (p for p in ("mpv", "ffplay") if shutil.which(p)), None)
    if el:
        row("OK" if player else "PARTIAL", "Speak (step 7)",
            f"key set, player: {player}" if player else "key set, but no audio player (mpv or ffplay); mp3 is saved only")
    else:
        row("SKIP", "Speak (step 7)", "needs ELEVENLABS_API_KEY")

    dsn = bool(os.environ.get("SENTRY_DSN", "").strip())
    row("OK" if dsn and has("sentry_sdk") else "SKIP", "Sentry (step 8)",
        "DSN set and sentry-sdk installed" if dsn and has("sentry_sdk")
        else "needs SENTRY_DSN" + ("" if has("sentry_sdk") else " and pip install sentry-sdk"))

    print("\nThis checks installs and settings only. It does not run any model or call any remote service.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
