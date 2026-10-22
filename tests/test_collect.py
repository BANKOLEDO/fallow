import csv
import os
import sys

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
