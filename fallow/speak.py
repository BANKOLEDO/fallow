"""Step 7 (optional): speak a line with ElevenLabs. Skips cleanly without a key."""
import argparse
import os
import platform
import shutil
import subprocess
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"   # ElevenLabs premade voice "Rachel"
MODEL_ID = "eleven_multilingual_v2"
TIMEOUT_S = 15


def player_cmd(path: str):
    if platform.system() == "Darwin":
        return ["afplay", path] if shutil.which("afplay") else None
    # aplay cannot decode MP3, so on Linux use a player that can.
    if shutil.which("mpv"):
        return ["mpv", "--no-video", "--really-quiet", path]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 7: optional voice line.")
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", default="out.mp3")
    args = ap.parse_args()

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("[SKIP] ELEVENLABS_API_KEY not set")
        return 0

    print("Requesting speech from ElevenLabs ...", flush=True)
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json={"text": args.text, "model_id": MODEL_ID},
            timeout=TIMEOUT_S,
        )
        if r.status_code != 200 or not r.content:
            print(f"[WARN] ElevenLabs returned HTTP {r.status_code}: {r.text[:150]}")
            return 0
        with open(args.out, "wb") as f:
            f.write(r.content)
        print(f"Saved {args.out} ({len(r.content)} bytes)")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] speech request failed: {type(e).__name__}: {str(e)[:150]}")
        return 0

    cmd = player_cmd(args.out)
    if cmd is None:
        print(f"[WARN] no audio player found (afplay on macOS, mpv or ffplay on Linux). {args.out} is saved.")
        return 0
    print(f"Playing with {cmd[0]} ...", flush=True)
    try:
        subprocess.run(cmd, check=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] playback failed ({type(e).__name__}); {args.out} was kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
