import sys

import pandas as pd

from fallow import report, site


def preds():
    return pd.DataFrame({
        "path": ["/a", "/b", "/c", "/d"], "name": ["old1.zip", "<script>x</script>.zip", "tmp.dmg", "keep.txt"],
        "ext": ["zip", "zip", "dmg", "txt"], "size_bytes": [1000, 2000, 2 * 1024 ** 3, 10],
        "age_days": [900, 700, 50, 3], "pred_label": [1, 1, 3, 2],
        "confidence_archive": [.9, .8, .1, .1], "confidence_keep": [.05, .1, .1, .8],
        "confidence_delete": [.05, .1, .8, .1],
    })


def test_report_numbers():
    text = report.build_report(preds())
    assert "Files analysed: 4" in text
    assert "Reclaimable space (predicted delete): 2.00 GB" in text
    assert text.index("old1.zip") < text.index("<script>")  # oldest first
    assert text.splitlines()[-1].startswith("Fallow triaged 4 files")


def test_site_escapes_file_names_and_matches_counts():
    page = site.build_page(preds())
    assert "<script>x</script>" not in page and "&lt;script&gt;" in page
    assert 'aria-label="Map of 4 files: 1 keep, 2 archive, 1 delete"' in page
    assert page.count('class="cell') == 4


def test_site_redact_hides_names_and_rename_table(tmp_path):
    ren = tmp_path / "r.csv"
    ren.write_text("path,old_name,new_name,description\n/a,old1.zip,clean.zip,secret thing\n")
    page = site.build_page(preds(), ren, redact=True)
    assert "old1.zip" not in page and "secret thing" not in page and "rename-title" not in page
    with_names = site.build_page(preds(), ren, redact=False)
    assert "clean.zip" in with_names and "secret thing" in with_names


def test_map_allocation_keeps_every_class_visible():
    cells = site.allocate({"k": 5000, "a": 3, "d": 0}, 400)
    assert sum(cells.values()) == 400 and cells["a"] >= 1 and cells["d"] == 0
    assert len(site.layout(cells)) == 400
