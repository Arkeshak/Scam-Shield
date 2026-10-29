"""Compare default Muse reasoning with low effort on 10 fixed synthetic messages."""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import analyze_text

CASES = [
    ("scam", "A fake delivery notice asks me to pay a fee through a shortened link."),
    ("scam", "A caller says to share my one-time login code to stop a payment."),
    ("scam", "A stranger promises guaranteed investment returns if I send crypto today."),
    ("scam", "A new-number message asks for urgent money and says not to tell family."),
    ("scam", "A pop-up says my computer is infected and asks me to install remote access."),
    ("safe", "Your one-time code is for sign-in. Never share it with anyone."),
    ("safe", "Your dentist appointment is tomorrow. Reply yes to confirm."),
    ("safe", "Your parcel shipped; track it in the shopping app you already use."),
    ("safe", "A monthly bill is ready in your usual utility app. No action is needed now."),
    ("safe", "A public guide says investments can lose value and past returns are not guaranteed."),
]


def main():
    for effort in (None, "low"):
        elapsed = []
        correct = 0
        for expected, text in CASES:
            started = time.perf_counter()
            result = analyze_text(text, reasoning_effort=effort)
            elapsed.append(time.perf_counter() - started)
            predicted = "scam" if result["risk"] in {"medium", "high"} else "safe"
            correct += predicted == expected
        label = "default" if effort is None else effort
        print(
            f"{label}: accuracy={correct}/{len(CASES)} "
            f"mean_latency={statistics.mean(elapsed):.2f}s"
        )


if __name__ == "__main__":
    main()
