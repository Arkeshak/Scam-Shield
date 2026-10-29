"""Measure SAM 3.1 box overlap on 25 synthetic UI screenshots (including harder layouts and safe controls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sam_refine import segment_concept, _iou

ROOT = Path(__file__).resolve().parents[1]
SCREENS_DIR = ROOT / "data" / "screens"
LABELS_FILE = SCREENS_DIR / "labels.json"


def simulate_rough_muse_box(expected: list[float]) -> list[float]:
    """Simulate the typical rough box returned by Muse Spark vision before SAM refinement."""
    x1, y1, x2, y2 = expected
    w, h = x2 - x1, y2 - y1
    # Expand slightly and shift
    rx1 = max(0.0, x1 - 0.04 * w)
    ry1 = max(0.0, y1 - 0.05 * h)
    rx2 = min(1.0, x2 + 0.06 * w)
    ry2 = min(1.0, y2 + 0.08 * h)
    return [round(rx1, 3), round(ry1, 3), round(rx2, 3), round(ry2, 3)]


def evaluate_screenshots():
    if not LABELS_FILE.is_file():
        raise SystemExit("Run tools/generate_eval_screens.py first to create images and labels.json")

    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))

    boxes_hit = 0
    boxes_missed = 0
    false_boxes_on_safe = 0
    sam_improved_count = 0
    total_evaluated_boxes = 0

    results_per_image = []

    print(f"Evaluating {len(labels)} screenshots with SAM 3.1...")

    for fname, meta in sorted(labels.items(), key=lambda kv: kv[1]["index"]):
        img_path = SCREENS_DIR / fname
        img_bytes = img_path.read_bytes()
        is_safe = meta.get("is_safe", False)
        concept = meta.get("concept", "button")
        expected_boxes = meta.get("expected_boxes", [])

        if is_safe:
            # On safe images, ask SAM for common prompt "button" or "link" to test for hallucinations/false positives
            pred_boxes = segment_concept(img_bytes, "image/png", "suspicious button")
            if pred_boxes:
                false_boxes_on_safe += len(pred_boxes)
                status = f"FALSE_BOXES ({len(pred_boxes)})"
            else:
                status = "CLEAN (no false boxes)"
            results_per_image.append({
                "filename": fname,
                "type": meta.get("type", "safe"),
                "is_safe": True,
                "status": status,
                "false_boxes": len(pred_boxes),
            })
            print(f"[{meta['index']:>2}/25] {fname} (SAFE): {status}")
        else:
            pred_boxes = segment_concept(img_bytes, "image/png", concept)
            pred_coords = [b["box"] for b in pred_boxes]

            img_hits = 0
            img_misses = 0
            for exp in expected_boxes:
                total_evaluated_boxes += 1
                best_iou = max((_iou(exp, p) for p in pred_coords), default=0.0)

                rough = simulate_rough_muse_box(exp)
                rough_iou = _iou(exp, rough)

                if best_iou >= 0.3:
                    boxes_hit += 1
                    img_hits += 1
                else:
                    boxes_missed += 1
                    img_misses += 1

                if best_iou > rough_iou:
                    sam_improved_count += 1

            status = f"hit={img_hits} miss={img_misses} best_iou={max((_iou(expected_boxes[0], p) for p in pred_coords), default=0.0):.2f}"
            results_per_image.append({
                "filename": fname,
                "type": meta.get("type", "synthetic"),
                "is_safe": False,
                "status": status,
                "boxes_hit": img_hits,
                "boxes_missed": img_misses,
            })
            print(f"[{meta['index']:>2}/25] {fname} ({meta['type']}): {status}")

    total_scam_screens = sum(1 for m in labels.values() if not m.get("is_safe"))
    total_safe_screens = sum(1 for m in labels.values() if m.get("is_safe"))

    eval_summary = {
        "total_images": len(labels),
        "scam_images": total_scam_screens,
        "safe_images": total_safe_screens,
        "total_expected_boxes": total_evaluated_boxes,
        "boxes_hit": boxes_hit,
        "boxes_missed": boxes_missed,
        "box_hit_rate": round(boxes_hit / total_evaluated_boxes, 3) if total_evaluated_boxes else 0.0,
        "iou_threshold": 0.3,
        "false_boxes_on_safe": false_boxes_on_safe,
        "sam_improved_on_rough_box_count": sam_improved_count,
        "sam_improved_rate": round(sam_improved_count / total_evaluated_boxes, 3) if total_evaluated_boxes else 0.0,
        "synthetic": True,
        "note": "Measured on synthetic and procedural UI screenshots. Harder cases include dark-mode SMS, cropped email, QR-code pretexts, and safe control receipts.",
    }

    # Store into data/eval_results.json
    results_file = ROOT / "data" / "eval_results.json"
    if results_file.is_file():
        data = json.loads(results_file.read_text(encoding="utf-8"))
        data["screenshot_evaluation"] = eval_summary
        results_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Store into data/eval_screenshots.json
    (ROOT / "data" / "eval_screenshots.json").write_text(
        json.dumps(eval_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("\n--- Screenshot Evaluation Summary ---")
    print(json.dumps(eval_summary, indent=2))
    return eval_summary


if __name__ == "__main__":
    evaluate_screenshots()
