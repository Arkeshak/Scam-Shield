"""STEP 10 - SAM 3.1 makes the marking sharper.

How it works:
  1. Muse Spark finds suspicious parts and gives each one a short noun phrase
     (like "logo", "button", "link text") plus a rough box.
  2. We send each noun phrase and the image to SAM 3.1 (model "sam-3.1").
  3. SAM 3.1 returns exact boxes. We keep the SAM box that best matches the rough box.
If SAM fails for any reason, we keep the rough box so the app still works.
Docs: https://dev.meta.ai/docs/media-segmentation  and  /docs/sam/reading-segmentation
"""
import base64
import io
import re
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from .annotate import normalize_box_fractions
from .llm import get_client

SAM_MODEL = "sam-3.1"

# Example from the docs:
# <0f>0<|box;x1=353;y1=382;x2=453;y2=427;w=537;h=561|><|mask;...|>,1<|box;...|>...
BOX_RE = re.compile(
    r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)(?:;c=([\d.]+))?\|>"
)


def segment_concept(image_bytes: bytes, mime: str, concept: str) -> list[dict]:
    """Ask SAM 3.1 for every match of `concept`. Returns boxes as fractions 0..1."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    text = ""
    with get_client().responses.stream(
        model=SAM_MODEL,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
                ],
            }
        ],
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                text += event.delta

    boxes = []
    for m in BOX_RE.finditer(text):
        x1, y1, x2, y2, w, h = (int(m.group(i)) for i in range(1, 7))
        if w == 0 or h == 0:
            continue
        boxes.append({"box": [x1 / w, y1 / h, x2 / w, y2 / h]})
    if not boxes and text:
        print(f"[SAM] raw response (no box tokens found): {text[:120]!r}")
    return boxes  # empty list = no match (this is normal, not an error)


def _iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


MAX_REGIONS = 4   # more boxes = more calls = slower; four is plenty for a screenshot


def _safe_segment(image_bytes: bytes, mime: str, concept: str) -> list[dict]:
    try:
        boxes = segment_concept(image_bytes, mime, concept)
        if not boxes:
            print(f"[SAM] no boxes returned for '{concept}'")
        return boxes
    except Exception as e:  # keep the app alive
        print(f"[SAM] failed for '{concept}': {e}")
        return []


def refine_with_sam(image_bytes: bytes, mime: str, regions: list[dict]) -> list[dict]:
    """Returns the same regions, with SAM 3.1 boxes where SAM found a match.
    SAM calls run IN PARALLEL (one per unique noun phrase), so 4 boxes cost about the same time as 1."""
    regions = list(regions)[:MAX_REGIONS]
    concepts = []
    for r in regions:
        raw = (r.get("sam_prompt") or r.get("label") or "").strip()
        # SAM works best with short visual noun phrases; truncate to 5 words
        c = " ".join(raw.split()[:5]) if raw else ""
        if c and c not in concepts:
            concepts.append(c)

    found: dict[str, list[dict]] = {}
    if concepts:
        with ThreadPoolExecutor(max_workers=len(concepts)) as pool:
            for concept, boxes in zip(concepts, pool.map(lambda c: _safe_segment(image_bytes, mime, c), concepts)):
                found[concept] = boxes

    w, h = 800, 600
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            w, h = im.size
    except Exception:
        pass

    refined = []
    for region in regions:
        region = dict(region)
        region["source"] = "muse"

        rough = region.get("box")
        if rough:
            norm = normalize_box_fractions(rough, w, h)
            if norm:
                region["box"] = norm
                rough = norm

        concept = (region.get("sam_prompt") or region.get("label") or "").strip()
        candidates = found.get(concept) or []
        best = None
        if candidates and rough and len(rough) == 4:
            score, cand = max(((_iou(rough, c["box"]), c) for c in candidates), key=lambda x: x[0])
            if score > 0.05:
                best = cand
        elif candidates:
            best = candidates[0]
        if best:
            region["box"] = best["box"]
            region["source"] = "sam-3.1"
        refined.append(region)
    return refined
