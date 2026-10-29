"""Optional text-only comparison against Baseten-hosted Muse Spark Open."""
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import RULES, RESULT_SHAPE, _extract_json

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://inference.baseten.co/v1"
MODEL = "meta-models/muse-spark-open"


def main():
    api_key = os.environ.get("BASETEN_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "Baseten comparison not run: set BASETEN_API_KEY in the local .env. "
            "No open-model results were produced."
        )

    client = OpenAI(base_url=BASE_URL, api_key=api_key)
    with (ROOT / "data" / "test_set.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    records, failures = [], []

    for index, row in enumerate(rows, start=1):
        language = row.get("language") or "English"
        prompt = (
            f"Check this fictional message for scams. Write all text fields in {language}.\n"
            f"MESSAGE:\n{row['text']}\n\nReturn JSON in this shape:\n{RESULT_SHAPE}"
        )
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": RULES},
                    {"role": "user", "content": prompt},
                ],
            )
            result = _extract_json(response.choices[0].message.content or "")
            predicted = "scam" if result.get("risk") in {"medium", "high"} else "safe"
            records.append({
                "expected": row["label"].strip().lower(),
                "predicted": predicted,
                "text": row["text"],
            })
            print(f"{index:>3}/{len(rows)} expected={row['label']:<5} predicted={predicted}")
        except Exception as e:
            failures.append({"index": index, "error": type(e).__name__})
            print(f"{index:>3}/{len(rows)} ERROR {type(e).__name__}")
        time.sleep(0.3)

    total = len(records)
    correct = sum(row["expected"] == row["predicted"] for row in records)
    output = {
        "provider": "Baseten Model APIs",
        "model": MODEL,
        "base_url": BASE_URL,
        "n": total,
        "total_cases": len(rows),
        "coverage": total / len(rows) if rows else 0,
        "accuracy": correct / total if total else 0,
        "false_alarms": sum(row["expected"] == "safe" and row["predicted"] == "scam" for row in records),
        "missed_scams": sum(row["expected"] == "scam" and row["predicted"] == "safe" for row in records),
        "failed_cases": failures,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    destination = ROOT / "data" / "open_model_eval_results.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Accuracy: {correct}/{total} = {output['accuracy']:.0%}; coverage: {total}/{len(rows)}")
    print(f"Results saved to {destination.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
