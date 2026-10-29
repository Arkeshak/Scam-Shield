"""Evaluate the text analyzer on synthetic datasets with CLI arguments."""
import argparse
import csv
import json
import time
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, RateLimitError
from app.llm import analyze_text

ROOT = Path(__file__).resolve().parent


def evaluate(file_path: str, out_path: str, label: str):
    path = Path(file_path)
    if not path.is_absolute():
        path = ROOT / path

    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise SystemExit(f"No evaluation cases found in {file_path}")

    results, wrong = [], []
    for index, row in enumerate(rows, start=1):
        lang = row.get("language") or "English"
        text = row["text"]
        expected = row["label"].strip().lower()

        res = None
        for attempt in range(4):
            try:
                res = analyze_text(text, lang)
                break
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                if attempt == 3:
                    print(f"{index:>3}/{len(rows)} ERROR {type(e).__name__} (4 attempts)")
                else:
                    delay = 2 ** attempt
                    print(f"{index:>3}/{len(rows)} transient API error; retry in {delay}s")
                    time.sleep(delay)
            except Exception as e:
                print(f"{index:>3}/{len(rows)} ERROR {type(e).__name__}: {e}")
                break

        risk = res.get("risk", "low") if res else "low"
        pred = "scam" if risk in ("medium", "high") else "safe"
        is_correct = (pred == expected)
        results.append(is_correct)

        if not is_correct:
            wrong.append({
                "text": text[:140],
                "expected": expected,
                "predicted": pred,
                "category": row.get("category", "")
            })

        print(f"{index:>3}/{len(rows)} expected={expected:<5} predicted={pred:<5} risk={risk:<6} {'OK' if is_correct else 'WRONG'}")
        time.sleep(0.2)

    n = len(rows)
    fa = sum(1 for w in wrong if w["predicted"] == "scam")
    ms = sum(1 for w in wrong if w["predicted"] == "safe")
    accuracy = round(sum(results) / n, 3) if n else 0

    out = {
        "label": label,
        "n": n,
        "accuracy": accuracy,
        "false_alarms": fa,
        "missed_scams": ms,
        "worst_cases": wrong[:5],
        "synthetic": True,
    }

    out_file = Path(out_path)
    if not out_file.is_absolute():
        out_file = ROOT / out_file
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nSummary:")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def main():
    parser = argparse.ArgumentParser(description="Evaluate text analyzer on synthetic dataset.")
    parser.add_argument("--file", default="data/test_set.csv", help="Path to input CSV file")
    parser.add_argument("--out", default="data/eval_results.json", help="Path to output JSON file")
    parser.add_argument("--label", default="development", help="Dataset label (development or unseen)")
    args = parser.parse_args()

    evaluate(args.file, args.out, args.label)


if __name__ == "__main__":
    main()
