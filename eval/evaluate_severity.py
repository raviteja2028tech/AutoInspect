"""Compare predicted overall severity with severity labels YOU assign by hand.

1. Copy eval/severity_labels_template.csv to eval/severity_labels.csv
2. For about 50 photos, write the image file name and the WORST severity you see:
   none / minor / moderate / severe
   (Use the same definitions as the prompt. Better: let a teammate label too.)
3. Run from the vision/ folder:

    python eval/evaluate_severity.py --labels eval/severity_labels.csv --images-dir data/my_images
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.analyse import AnalysisError, analyse_image  # noqa: E402
from src.intake import IntakeError, load_image          # noqa: E402
from src.vocab import SEVERITY_RANK                      # noqa: E402

ORDER = ["none", "minor", "moderate", "severe"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(args.labels)
    rows = []
    for _, r in labels.iterrows():
        truth = str(r["severity"]).strip().lower()
        try:
            img = load_image(Path(args.images_dir) / r["image"])
            res = analyse_image(img.jpeg_bytes)
        except (IntakeError, AnalysisError) as exc:
            print(f"SKIP {r['image']}: {exc}")
            continue
        sev = [d.severity for d in res.damages if d.confidence >= args.threshold]
        pred = max(sev, key=SEVERITY_RANK.get) if sev else "none"
        rows.append({"image": r["image"], "truth": truth, "pred": pred})
        print(f"{r['image']}: truth={truth} pred={pred}")

    if not rows:
        raise SystemExit("Nothing evaluated.")
    df = pd.DataFrame(rows)
    df.to_csv(out / "severity_predictions.csv", index=False)
    exact = (df["truth"] == df["pred"]).mean()
    within1 = ((df["truth"].map(ORDER.index) - df["pred"].map(ORDER.index)).abs() <= 1).mean()
    cm = pd.crosstab(pd.Categorical(df["truth"], ORDER), pd.Categorical(df["pred"], ORDER), dropna=False)
    cm.to_csv(out / "severity_confusion.csv")
    print(f"\nExact agreement: {exact:.3f}   Within one level: {within1:.3f}   (n={len(df)})")
    print("\nRows = your label, columns = model:")
    print(cm.to_string())


if __name__ == "__main__":
    main()
