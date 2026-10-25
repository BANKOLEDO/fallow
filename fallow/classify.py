"""Step 3: train a classifier on your labels and print an honest evaluation.

Resolution order: local TabPFN -> Prior Labs API (TabPFN) -> sklearn RandomForest.
The script always finishes and always prints an accuracy figure.
"""
import argparse
import os
import sys
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

NUMERIC = ["size_bytes", "age_days", "mtime_days", "is_hidden", "depth", "name_len", "has_number_in_name"]
CLASSES = [1, 2, 3]
NAMES = {1: "archive", 2: "keep", 3: "delete"}
MAX_CATS = 30          # keep one-hot width sane on an 8GB CPU box; rarer values -> "other"
API_TIMEOUT_S = 120    # whole fit+predict call through the hosted API


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    X = df[NUMERIC].astype(float).copy()
    for col in ("ext", "parent_folder"):
        s = df[col].fillna("").astype(str)
        keep = set(s.value_counts().head(MAX_CATS).index)
        s = s.where(s.isin(keep), "other")
        X = pd.concat([X, pd.get_dummies(s, prefix=col).astype(float)], axis=1)
    return X


def _run_with_timeout(fn, seconds):
    """Run fn in a daemon thread so a stuck network call cannot hang the script."""
    out = {}

    def target():
        try:
            out["value"] = fn()
        except BaseException as e:  # noqa: BLE001
            out["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"no response after {seconds}s")
    if "error" in out:
        raise out["error"]
    return out["value"]


def _try_local_tabpfn(Xtr, ytr, Xall):
    os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")
    from tabpfn import TabPFNClassifier  # ImportError if not installed
    print("[INFO] fitting TabPFN locally on CPU (can take a few minutes) ...", flush=True)
    clf = TabPFNClassifier(device="cpu")
    clf.fit(Xtr, ytr)
    return "TabPFN (local)", clf.classes_, clf.predict_proba(Xall), clf


def _try_tabpfn_api(Xtr, ytr, Xall):
    token = os.environ.get("TABPFN_API_KEY", "").strip()
    if not token:
        raise RuntimeError("TABPFN_API_KEY not set")
    import tabpfn_client  # ImportError if not installed
    from tabpfn_client import TabPFNClassifier

    def go():
        tabpfn_client.set_access_token(token)
        clf = TabPFNClassifier()
        clf.fit(Xtr, ytr)
        return clf.classes_, clf.predict_proba(Xall), clf

    print("[INFO] calling the TabPFN API ...", flush=True)
    classes, proba, clf = _run_with_timeout(go, API_TIMEOUT_S)
    return "TabPFN (Prior Labs API)", classes, proba, clf


def _rf(Xtr, ytr, Xall):
    print("!" * 60, flush=True)
    print("[WARN] FALLBACK CLASSIFIER — results are NOT TabPFN", flush=True)
    print("!" * 60, flush=True)
    clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    clf.fit(Xtr, ytr)
    return "RandomForest (fallback)", clf.classes_, clf.predict_proba(Xall), clf


def classify(Xtr, ytr, Xall):
    """Returns (name, classes_, proba over Xall, fitted clf). Never raises."""
    try:
        return _try_local_tabpfn(Xtr, ytr, Xall)
    except BaseException as e:  # noqa: BLE001 - OOM, import error, missing weights, anything
        if isinstance(e, KeyboardInterrupt):
            raise
        print(f"[WARN] local TabPFN unavailable: {type(e).__name__}: {str(e)[:200]}", flush=True)
    try:
        res = _try_tabpfn_api(Xtr, ytr, Xall)
        print("[INFO] using TabPFN API (local install failed)", flush=True)
        return res
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, KeyboardInterrupt):
            raise
        print(f"[WARN] TabPFN API unavailable: {type(e).__name__}: {str(e)[:200]}", flush=True)
    return _rf(Xtr, ytr, Xall)


def to_full_proba(classes, proba):
    """Reorder predict_proba columns to [1, 2, 3]; absent classes get 0."""
    full = np.zeros((proba.shape[0], 3))
    for j, c in enumerate(classes):
        full[:, CLASSES.index(int(c))] = proba[:, j]
    return full


def main() -> int:
    ap = argparse.ArgumentParser(description="Fallow step 3: classify files.")
    ap.add_argument("--file", default="fallow_data.csv")
    ap.add_argument("--out", default="fallow_predictions.csv")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"[ERROR] {args.file} not found. Run collect and label first.")
        return 1
    df = pd.read_csv(args.file, keep_default_na=False)
    df["label_n"] = pd.to_numeric(df["label"], errors="coerce")
    lab = df[df["label_n"].isin(CLASSES)].copy()
    lab["label_n"] = lab["label_n"].astype(int)

    if len(lab) < 10 or lab["label_n"].nunique() < 2:
        print(f"[ERROR] need at least 10 labelled rows covering 2+ classes (have {len(lab)}). Run fallow.label.")
        return 1

    X_all = build_features(df)
    X = X_all.loc[lab.index]
    y = lab["label_n"]

    counts = y.value_counts()
    can_stratify = counts.min() >= 2 and len(lab) * 0.2 >= y.nunique()
    if not can_stratify:
        print("[WARN] a class has <2 rows or the set is tiny; using a NON-stratified split.")
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if can_stratify else None
    )

    print("=== DATASET ===")
    print(f"rows used: {len(lab)}  (train {len(Xtr)} / holdout {len(Xte)})")
    print("class balance: " + "  ".join(f"{c}={NAMES[c]}:{int(counts.get(c, 0))}" for c in CLASSES))

    from fallow import tracing
    tracing.init()
    with tracing.span("fallow.classify"):
        name, classes, proba_all, clf = classify(Xtr, ytr, X_all)

    proba = to_full_proba(classes, proba_all)
    pred = np.array(CLASSES)[proba.argmax(axis=1)]
    pred_s = pd.Series(pred, index=df.index)

    te_pred = pred_s.loc[Xte.index].to_numpy()
    acc = accuracy_score(yte, te_pred)
    p, r, _, sup = precision_recall_fscore_support(yte, te_pred, labels=CLASSES, zero_division=0)
    cm = confusion_matrix(yte, te_pred, labels=CLASSES)

    print("\n=== RESULT ===")
    print(f"classifier: {name}")
    print(f"accuracy: {acc:.3f}  ({int((te_pred == yte.to_numpy()).sum())}/{len(yte)} holdout rows correct)")
    print(f"{'class':<10}{'precision':>10}{'recall':>9}{'support':>9}")
    for i, c in enumerate(CLASSES):
        print(f"{c}={NAMES[c]:<8}{p[i]:>10.3f}{r[i]:>9.3f}{int(sup[i]):>9}")
    print("confusion matrix (rows = true, cols = predicted):")
    print(f"{'':>12}" + "".join(f"{'pred_' + NAMES[c]:>13}" for c in CLASSES))
    for i, c in enumerate(CLASSES):
        print(f"{'true_' + NAMES[c]:>12}" + "".join(f"{int(v):>13}" for v in cm[i]))

    wrong = Xte.index[te_pred != yte.to_numpy()]
    print("\n=== MISCLASSIFIED ===")
    print(f"{len(wrong)} of {len(yte)} holdout rows were wrong")
    for idx in list(wrong)[:3]:
        print(f"  {df.at[idx, 'name']}  | true={NAMES[int(lab.at[idx, 'label_n'])]}  predicted={NAMES[int(pred_s[idx])]}")

    print("\n=== FEATURE IMPORTANCE ===")
    importances = getattr(clf, "feature_importances_", None)
    if importances is None:
        print("(classifier does not expose feature importances)")
    else:
        feat_names = list(X.columns)
        pairs = sorted(zip(feat_names, importances), key=lambda x: x[1], reverse=True)[:10]
        for fname, imp in pairs:
            print(f"  {fname:<28}{imp:.4f}")

    out = pd.DataFrame({
        "path": df["path"], "name": df["name"], "ext": df["ext"],
        "size_bytes": df["size_bytes"], "age_days": df["age_days"],
        "true_label": df["label_n"].where(df["label_n"].isin(CLASSES)).astype("Int64"),
        "pred_label": pred_s,
        "confidence_archive": proba[:, 0].round(4),
        "confidence_keep": proba[:, 1].round(4),
        "confidence_delete": proba[:, 2].round(4),
    })
    out.to_csv(args.out, index=False)

    print("\n=== TOP ARCHIVE CANDIDATES ===")
    cand = out[(out["pred_label"] == 1) & (out["age_days"].astype(float) > 180)]
    cand = cand.sort_values("confidence_archive", ascending=False).head(15)
    if cand.empty:
        print("(none: no predicted-archive files older than 180 days)")
    else:
        w = min(48, max(len(n) for n in cand["name"]) + 1)
        print(f"{'name':<{w}}| {'age_days':>9} | confidence")
        for _, row in cand.iterrows():
            print(f"{row['name'][:w - 1]:<{w}}| {float(row['age_days']):>9.1f} | {row['confidence_archive']:.3f}")

    print(f"\nPredictions for all {len(out)} collected files written to {args.out}")
    print("(rows with empty true_label were never labelled; rows you labelled for training are in-sample)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
