"""Evaluate damage-TYPE detection against the CarDD ground truth.

Run from the vision/ folder (after setting GEMINI_API_KEY):

    python eval/evaluate.py --annotations data/CarDD/<annotations>.json --images-dir data/CarDD/<images folder> --n 60

CarDD annotations are COCO-style JSON. Use the TEST split JSON and its matching
image folder. Results are cached, so re-running is free. Start with --n 20.
Output goes to eval/results/.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.analyse import AnalysisError, analyse_image  # noqa: E402
from src.intake import IntakeError, load_image          # noqa: E402
from src.vocab import DAMAGE_TYPES                       # noqa: E402


def norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotations", required=True, help="COCO-style JSON file from CarDD")
    ap.add_argument("--images-dir", required=True, help="folder with the matching images")
    ap.add_argument("--n", type=int, default=60, help="how many images to test")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--threshold", type=float, default=0.5, help="ignore predictions below this confidence")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    images_dir = Path(args.images_dir)

    coco = json.loads(Path(args.annotations).read_text(encoding="utf-8"))
    cat = {c["id"]: norm(c["name"]) for c in coco["categories"]}
    unmapped = sorted({n for n in cat.values() if n not in DAMAGE_TYPES})
    if unmapped:
        print(f"WARNING: these dataset classes are not in our DAMAGE_TYPES and will be ignored: {unmapped}")

    gt = defaultdict(set)
    for a in coco["annotations"]:
        name = cat[a["category_id"]]
        if name in DAMAGE_TYPES:
            gt[a["image_id"]].add(name)
    files = {i["id"]: i["file_name"] for i in coco["images"]}

    ids = sorted(i for i in files if i in gt)
    random.Random(args.seed).shuffle(ids)
    ids = ids[: args.n]
    print(f"Evaluating {len(ids)} images (threshold {args.threshold}) ...")

    rows, skipped = [], 0
    for k, image_id in enumerate(ids, 1):
        fname = files[image_id]
        path = images_dir / Path(fname).name
        if not path.exists():
            path = images_dir / fname
        try:
            img = load_image(path)
            res = analyse_image(img.jpeg_bytes)
        except (IntakeError, AnalysisError) as exc:
            print(f"  [{k}/{len(ids)}] SKIP {fname}: {exc}")
            skipped += 1
            continue

        best = {}                                    # highest confidence per predicted type
        for d in res.damages:
            best[d.damage_type] = max(best.get(d.damage_type, 0.0), d.confidence)
        pred = {t for t, c in best.items() if c >= args.threshold}
        rows.append({"image": fname, "truth": sorted(gt[image_id]), "pred": sorted(pred), "conf": best})
        print(f"  [{k}/{len(ids)}] {fname}: truth={sorted(gt[image_id])} pred={sorted(pred)}")

    if not rows:
        raise SystemExit("No images were evaluated. Check --images-dir and your API key.")

    # ---- per-class precision / recall / F1 ----
    metrics = []
    for t in DAMAGE_TYPES:
        tp = sum(1 for r in rows if t in r["truth"] and t in r["pred"])
        fp = sum(1 for r in rows if t not in r["truth"] and t in r["pred"])
        fn = sum(1 for r in rows if t in r["truth"] and t not in r["pred"])
        p = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        metrics.append({"class": t, "support": tp + fn, "precision": round(p, 3),
                        "recall": round(rc, 3), "f1": round(f1, 3)})
    mdf = pd.DataFrame(metrics)
    TP = sum(len(set(r["truth"]) & set(r["pred"])) for r in rows)
    FP = sum(len(set(r["pred"]) - set(r["truth"])) for r in rows)
    FN = sum(len(set(r["truth"]) - set(r["pred"])) for r in rows)
    mp = TP / (TP + FP) if TP + FP else 0.0
    mr = TP / (TP + FN) if TP + FN else 0.0
    micro_f1 = 2 * mp * mr / (mp + mr) if mp + mr else 0.0
    exact = sum(1 for r in rows if set(r["truth"]) == set(r["pred"])) / len(rows)
    any_found = sum(1 for r in rows if r["pred"]) / len(rows)
    mdf.to_csv(out / "metrics_per_class.csv", index=False)

    # ---- confidence calibration ----
    cal = []
    for r in rows:
        for t, c in r["conf"].items():
            cal.append({"conf": c, "correct": t in r["truth"]})
    cdf = pd.DataFrame(cal)
    if not cdf.empty:
        cdf["bucket"] = pd.cut(cdf["conf"], [0, 0.5, 0.7, 0.9, 1.0001], right=False,
                               labels=["<0.5", "0.5-0.7", "0.7-0.9", "0.9-1.0"])
        cal_table = cdf.groupby("bucket", observed=True)["correct"].agg(["count", "mean"]).rename(
            columns={"mean": "accuracy"}).round(3)
        cal_table.to_csv(out / "calibration.csv")
    else:
        cal_table = pd.DataFrame()

    # ---- confusion matrix (images with exactly ONE true damage type) ----
    conf_rows = []
    for r in rows:
        if len(r["truth"]) == 1:
            top = max(r["pred"], key=lambda t: r["conf"][t]) if r["pred"] else "none"
            conf_rows.append((r["truth"][0], top))
    if conf_rows:
        labels = DAMAGE_TYPES + ["none"]
        cm = pd.crosstab(pd.Categorical([a for a, _ in conf_rows], DAMAGE_TYPES),
                         pd.Categorical([b for _, b in conf_rows], labels), dropna=False)
        cm.to_csv(out / "confusion_matrix.csv")
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.imshow(cm.values, cmap="Blues")
        ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        ax.set_yticks(range(len(DAMAGE_TYPES)), DAMAGE_TYPES)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, int(cm.values[i, j]), ha="center", va="center")
        ax.set_xlabel("Predicted (top prediction)")
        ax.set_ylabel("True (single-damage images)")
        ax.set_title("Confusion matrix")
        fig.tight_layout()
        fig.savefig(out / "confusion_matrix.png", dpi=150)
        plt.close(fig)

    # ---- bar chart ----
    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(mdf))
    ax.bar([i - 0.2 for i in x], mdf["precision"], 0.4, label="precision")
    ax.bar([i + 0.2 for i in x], mdf["recall"], 0.4, label="recall")
    ax.set_xticks(list(x), mdf["class"], rotation=30, ha="right")
    ax.set_ylim(0, 1)
    ax.set_title(f"Per-class results ({len(rows)} images)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "per_class.png", dpi=150)
    plt.close(fig)

    pd.DataFrame([{"image": r["image"], "truth": ",".join(r["truth"]), "pred": ",".join(r["pred"])}
                  for r in rows]).to_csv(out / "predictions.csv", index=False)

    print("\n===== RESULTS =====")
    print(f"Images evaluated: {len(rows)} (skipped {skipped})")
    print(mdf.to_string(index=False))
    print(f"\nMicro precision {mp:.3f} | recall {mr:.3f} | F1 {micro_f1:.3f}")
    print(f"Exact-match (all types right): {exact:.3f}")
    print(f"Images where some damage was found: {any_found:.3f}")
    if not cal_table.empty:
        print("\nConfidence calibration (does accuracy rise with confidence?):")
        print(cal_table.to_string())
    print(f"\nFiles saved in {out}")


if __name__ == "__main__":
    main()
