"""Measures REAL speed of each pipeline stage, before and after the speed fixes (uses about 10 API calls, run once).
  python tools/time_pipeline.py data/demo_screenshot.png
Compare the lines: full agent vs fast mode, serial SAM vs parallel SAM, big image vs shrunk image."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, sam_refine
from app.agent import AgentContext, run_agent, run_agent_fast
from app.annotate import shrink_image
from app.llm import analyze_image, get_client

TEXT = "URGENT: Your bank account is locked. Verify now at http://secure-b4nk-login.xyz/verify or it will close in 2 hours."
rows = []


def timed(label, fn):
    t = time.perf_counter()
    try:
        out = fn()
    except Exception as e:
        out = None
        label += f"  (FAILED: {str(e)[:60]})"
    s = time.perf_counter() - t
    rows.append((label, s))
    print(f"{s:6.1f}s  {label}")
    return out


print(f"model: {config.MODEL_NAME}\n")
timed("floor: one tiny Muse Spark call ('say hi')", lambda: get_client().responses.create(model=config.MODEL_NAME, input="Say hi in one word."))
timed("text: FULL agent (tool-calling loop)", lambda: run_agent(TEXT, AgentContext(), "English"))
timed("text: FAST mode (one model call)", lambda: run_agent_fast(TEXT, AgentContext(), "English"))

if len(sys.argv) > 1:
    big = open(sys.argv[1], "rb").read()
    mime = "image/png" if sys.argv[1].lower().endswith("png") else "image/jpeg"
    small, smime = shrink_image(big)
    print(f"\nimage bytes: original {len(big):,} -> shrunk {len(small):,}")
    timed("vision: original image", lambda: analyze_image(big, mime, "English"))
    vision = timed("vision: shrunk image", lambda: analyze_image(small, smime, "English"))
    regions = (vision or {}).get("regions", [])[:4]
    concepts = [(r.get("sam_prompt") or r.get("label") or "").strip() for r in regions]
    concepts = [c for i, c in enumerate(concepts) if c and c not in concepts[:i]]
    if not concepts:
        concepts = ["claim prize button", "prize notification text"]
    print(f"SAM concepts: {concepts}")

    def serial():
        return [sam_refine._safe_segment(small, smime, c) for c in concepts]

    timed(f"SAM: {len(concepts)} calls one after another", serial)
    timed(f"SAM: same {len(concepts)} calls in parallel (refine_with_sam)", lambda: sam_refine.refine_with_sam(small, smime, regions if regions else [{"label": c, "sam_prompt": c} for c in concepts]))

print("\nWrite these numbers into docs/SPEED_RESULTS.md (real numbers only).")
