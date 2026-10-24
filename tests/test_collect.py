import csv
import os
import sys
import time

from fallow import collect
from tests.helpers import make_rows, write_csv


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["collect", *args])
    return collect.main()


def test_skips_ignored_dirs_and_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "scan"
    for d in (".git", "node_modules", "venv", "docs", ".hidden"):
        (root / d).mkdir(parents=True)
    (root / "docs" / "report_2023.pdf").write_text("x")
    (root / ".hidden" / "s.cfg").write_text("x")
    (root / ".git" / "c").write_text("x")
    (root / "node_modules" / "n.js").write_text("x")
    (root / "venv" / "v.py").write_text("x")
    try:
        os.symlink(root / "docs" / "report_2023.pdf", root / "link")
        has_symlink = True
    except OSError:
        has_symlink = False
    out = tmp_path / "out.csv"
    assert run(monkeypatch, "--dir", str(root), "--out", str(out)) == 0
    rows = list(csv.DictReader(open(out)))
    names = {r["name"] for r in rows}
    assert names == {"report_2023.pdf", "s.cfg"}
    by = {r["name"]: r for r in rows}
    assert by["s.cfg"]["is_hidden"] == "1" and by["report_2023.pdf"]["is_hidden"] == "0"
    assert by["report_2023.pdf"]["has_number_in_name"] == "1"
    assert by["report_2023.pdf"]["label"] == ""


def test_caps_file_count(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "MAX_FILES", 5)
    root = tmp_path / "scan"
    root.mkdir()
    for i in range(12):
        (root / f"f{i}.txt").write_text("x")
    out = tmp_path / "out.csv"
    run(monkeypatch, "--dir", str(root), "--out", str(out))
    assert len(list(csv.DictReader(open(out)))) == 5


def test_refuses_to_erase_labels_unless_forced(tmp_path, monkeypatch, capsys):
    root = tmp_path / "scan"
    root.mkdir()
    (root / "a.txt").write_text("x")
    out = tmp_path / "out.csv"
    write_csv(out, make_rows(10, labelled=4))
    assert run(monkeypatch, "--dir", str(root), "--out", str(out)) == 1
    assert "4 labels" in capsys.readouterr().out
    assert sum(1 for r in csv.DictReader(open(out)) if r["label"]) == 4  # untouched
    assert run(monkeypatch, "--dir", str(root), "--out", str(out), "--force") == 0


def test_autolabel_marks_obvious_files(tmp_path, monkeypatch):
    root = tmp_path / "scan"
    root.mkdir()
    (root / "cache.tmp").write_text("x")
    (root / "old.zip").write_text("x")
    (root / "recent.jpg").write_text("x")
    (root / "mystery.xyz").write_text("x")
    import os
    old_mtime = time.time() - 400 * 86400
    recent_mtime = time.time() - 5 * 86400
    os.utime(root / "old.zip", (old_mtime, old_mtime))
    os.utime(root / "recent.jpg", (recent_mtime, recent_mtime))
    out = tmp_path / "out.csv"
    assert run(monkeypatch, "--dir", str(root), "--out", str(out), "--autolabel") == 0
    by = {r["name"]: r for r in csv.DictReader(open(out))}
    assert by["cache.tmp"]["label"] == "3" and by["cache.tmp"]["label_source"] == "auto"
    assert by["old.zip"]["label"] == "1" and by["old.zip"]["label_source"] == "auto"
    assert by["recent.jpg"]["label"] == "2" and by["recent.jpg"]["label_source"] == "auto"
    assert by["mystery.xyz"]["label"] == "" and by["mystery.xyz"]["label_source"] == ""
