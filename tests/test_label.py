import csv
import os
import sys

from fallow import label
from tests.helpers import make_rows, write_csv


def run(monkeypatch, path, keys):
    it = iter(keys)
    monkeypatch.setattr(label, "getkey", lambda: next(it))
    monkeypatch.setattr(sys, "argv", ["label", "--file", str(path)])
    return label.main()


def labels(path):
    return [r["label"] for r in csv.DictReader(open(path))]


def test_saves_each_label_and_resumes_at_first_unlabelled(tmp_path, monkeypatch):
    p = tmp_path / "d.csv"
    write_csv(p, make_rows(5, labelled=0))
    run(monkeypatch, p, ["1", "s", "2", "q"])
    assert labels(p)[:4] == ["1", "", "2", ""]
    run(monkeypatch, p, ["3", "q"])          # resumes at the row that was skipped
    assert labels(p)[:3] == ["1", "3", "2"]


def test_quit_midway_keeps_earlier_labels_and_leaves_no_temp_files(tmp_path, monkeypatch):
    p = tmp_path / "d.csv"
    write_csv(p, make_rows(4, labelled=0))
    run(monkeypatch, p, ["1", "1", "q"])
    assert labels(p)[:2] == ["1", "1"]
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_prints_200_label_notice_once(tmp_path, monkeypatch, capsys):
    p = tmp_path / "d.csv"
    write_csv(p, make_rows(203, labelled=198))
    run(monkeypatch, p, ["1", "1", "1", "1", "1", "q"])
    assert capsys.readouterr().out.count("200 labels reached") == 1


def test_review_only_prompts_unlabeled(tmp_path, monkeypatch, capsys):
    p = tmp_path / "d.csv"
    rows = make_rows(4, labelled=0)
    rows[0]["label"] = "2"; rows[0]["label_source"] = ""          # user-labelled
    rows[1]["label"] = "1"; rows[1]["label_source"] = "auto"      # auto-labelled
    rows[2]["label"] = "3"; rows[2]["label_source"] = ""          # user-labelled
    # only row index 3 is unlabeled -> should be prompted
    write_csv(p, rows)
    it = iter(["1", "q"])
    monkeypatch.setattr(label, "getkey", lambda: next(it))
    monkeypatch.setattr(sys, "argv", ["label", "--file", str(p), "--review"])
    rc = label.main()
    assert rc == 0
    text = capsys.readouterr().out
    assert "auto" in text
    prompt_lines = [l for l in text.splitlines() if l.startswith("[") and "] " in l]
    assert len(prompt_lines) == 1
    assert "[3]" in prompt_lines[0]
