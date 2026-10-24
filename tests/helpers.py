import csv
import random

COLUMNS = ["path", "name", "ext", "size_bytes", "age_days", "mtime_days", "is_hidden",
           "parent_folder", "depth", "name_len", "has_number_in_name", "label", "label_source"]


def make_rows(n=120, labelled=100, seed=0):
    """Synthetic file rows where the label really depends on age and extension."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        ext = rnd.choice(["pdf", "zip", "dmg", "txt", "jpg"])
        age = rnd.choice([5, 40, 250, 600]) + rnd.random() * 10
        label = 3 if ext == "dmg" and age > 100 else 1 if age > 180 else 2
        name = f"file_{i}.{ext}"
        rows.append({
            "path": f"/x/{name}", "name": name, "ext": ext,
            "size_bytes": rnd.randint(1_000, 5_000_000), "age_days": round(age, 2),
            "mtime_days": round(age, 2), "is_hidden": 0,
            "parent_folder": rnd.choice(["Downloads", "old"]), "depth": 0,
            "name_len": len(name), "has_number_in_name": 1,
            "label": label if i < labelled else "", "label_source": "",
        })
    return rows


def write_csv(path, rows, fields=COLUMNS):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
