import sys

import pandas as pd

from fallow import classify
from tests.helpers import make_rows, write_csv


def boom(*a, **k):
    raise ImportError("forced for test")


def run(monkeypatch, tmp_path, rows):
    data, out = tmp_path / "d.csv", tmp_path / "p.csv"
    write_csv(data, rows)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setattr(classify, "_try_local_tabpfn", boom)
    monkeypatch.setattr(classify, "_try_tabpfn_api", boom)
    monkeypatch.setattr(sys, "argv", ["classify", "--file", str(data), "--out", str(out)])
    return classify.main(), out


def test_falls_back_loudly_and_prints_sections_in_order(tmp_path, monkeypatch, capsys):
    rc, out = run(monkeypatch, tmp_path, make_rows(160, labelled=140))
    text = capsys.readouterr().out
    assert rc == 0
    assert "[WARN] local TabPFN unavailable" in text
    assert "[WARN] FALLBACK CLASSIFIER — results are NOT TabPFN" in text
    marks = ["=== DATASET ===", "=== RESULT ===", "=== MISCLASSIFIED ===", "=== TOP ARCHIVE CANDIDATES ==="]
    positions = [text.index(m) for m in marks]
    assert positions == sorted(positions)
    assert "accuracy:" in text and "confusion matrix" in text
    pred = pd.read_csv(out)
    assert list(pred.columns) == ["path", "name", "ext", "size_bytes", "age_days", "true_label",
                                  "pred_label", "confidence_archive", "confidence_keep", "confidence_delete"]
    assert len(pred) == 160
    assert (pred[["confidence_archive", "confidence_keep", "confidence_delete"]].sum(axis=1).round(3) == 1).all()


def test_candidate_table_is_old_confident_and_capped(tmp_path, monkeypatch, capsys):
    # Many young pdfs are archive and only a few old files exist, so without the
    # age filter the table would fill up with young files.
    rows = make_rows(200, labelled=170)
    for r in rows:
        i = int(r["name"].split("_")[1].split(".")[0])
        if r["age_days"] >= 100 and i % 9:  # keep only about one file in nine old
            r["age_days"] = r["mtime_days"] = 5.0
        young = r["age_days"] < 100
        if r["label"] and young:
            r["label"] = 1 if r["ext"] == "pdf" else 2
    rc, out = run(monkeypatch, tmp_path, rows)
    text = capsys.readouterr().out
    block = text.split("=== TOP ARCHIVE CANDIDATES ===")[1].split("Predictions for all")[0].strip().splitlines()[1:]
    pred = pd.read_csv(out).set_index("name")
    young_archive = ((pred.pred_label == 1) & (pred.age_days <= 180)).sum()
    assert young_archive >= 15  # the filter has plenty to exclude
    assert len(block) <= 15
    confs = []
    for line in block:
        name = line.split("|")[0].strip()
        assert pred.loc[name, "age_days"] > 180 and pred.loc[name, "pred_label"] == 1
        confs.append(float(line.split("|")[-1]))
    assert confs == sorted(confs, reverse=True)


def test_always_finishes_with_a_missing_class(tmp_path, monkeypatch, capsys):
    rows = make_rows(40, labelled=40)
    for r in rows:
        if r["label"] == 3:
            r["label"] = 2
    rows[0]["label"] = 3  # exactly one row of class 3: stratified split is impossible
    rc, _ = run(monkeypatch, tmp_path, rows)
    text = capsys.readouterr().out
    assert rc == 0 and "accuracy:" in text and "NON-stratified" in text


def test_too_few_labels_is_a_clear_error(tmp_path, monkeypatch, capsys):
    rc, _ = run(monkeypatch, tmp_path, make_rows(30, labelled=5))
    assert rc == 1 and "need at least 10 labelled rows" in capsys.readouterr().out
