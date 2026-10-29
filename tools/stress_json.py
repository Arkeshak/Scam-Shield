"""Make 20 small live Muse Spark calls and verify the structured response shape."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import analyze_text


def main():
    valid = 0
    for index in range(20):
        result = analyze_text(
            f"Fictional test {index + 1}: A person says hello and asks whether the library is open."
        )
        required = {"risk", "scam_type", "verdict", "reasons", "red_flags", "next_step", "confidence"}
        if not required.issubset(result):
            raise RuntimeError(f"Call {index + 1} is missing required fields")
        if result["risk"] not in {"low", "medium", "high"}:
            raise RuntimeError(f"Call {index + 1} returned an invalid risk value")
        if not isinstance(result["reasons"], list) or not isinstance(result["red_flags"], list):
            raise RuntimeError(f"Call {index + 1} returned invalid list fields")
        valid += 1
    print(f"Structured JSON calls passed: {valid}/20")


if __name__ == "__main__":
    main()
