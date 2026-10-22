import sys

import requests

from fallow import prose, rename, speak


def test_rename_rejects_boilerplate_stems():
    assert rename._looks_valid("invoice_2023_q4", "zip") is True
    assert rename._looks_valid("file", "zip") is False
    assert rename._looks_valid(rename.BOILERPLATE.pop() if False else "a_clean_human_readable_snake_case_filename_stem", "zip") is False
    assert rename._looks_valid("clean_human_readable_snake_case_filename", "zip") is False
    assert rename._looks_valid("zip", "zip") is False


def test_rename_falls_back_to_original_name_on_garbage_json(monkeypatch):
    class R:
        status_code = 200
        text = "not json"
        def raise_for_status(self):
            pass
    monkeypatch.setattr(rename.requests, "post", lambda *a, **k: R())
    res = rename.ask("gemma3:270m", "old_report.pdf", "pdf", 1000, 200.0)
    assert res["stem"] == "old_report"  # fell back to original name stem
    assert res["description"] == ""


def test_prose_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ULTRAMARINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["prose"])
    assert prose.main() == 0
    assert "[SKIP]" in capsys.readouterr().out


def test_speak_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["speak", "--text", "hi"])
    assert speak.main() == 0
    assert "[SKIP] ELEVENLABS_API_KEY not set" in capsys.readouterr().out


def test_rename_skips_when_ollama_is_down(monkeypatch, capsys):
    def down(*a, **k):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(rename.requests, "get", down)
    monkeypatch.setattr(sys, "argv", ["rename"])
    assert rename.main() == 0
    assert "[SKIP] Ollama not reachable" in capsys.readouterr().out


def test_speak_keeps_mp3_when_playback_fails(monkeypatch, tmp_path, capsys):
    class R:
        status_code, content, text = 200, b"ID3audio", ""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(speak.requests, "post", lambda *a, **k: R())
    monkeypatch.setattr(speak, "player_cmd", lambda p: ["definitely-not-a-player", p])
    out = tmp_path / "o.mp3"
    monkeypatch.setattr(sys, "argv", ["speak", "--text", "hi", "--out", str(out)])
    assert speak.main() == 0
    assert out.exists() and "playback failed" in capsys.readouterr().out
