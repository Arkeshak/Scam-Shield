"""Draws high-visibility boxes, tinted overlays, and number badges on screenshots."""
import base64
import io

from PIL import Image, ImageDraw, ImageFont


def normalize_box(box_raw, w: int, h: int) -> list[float] | None:
    """Normalizes any bounding box (fractions 0..1, 0..1000 scale, pixels, percentages)
    into standard pixel coordinates [x1, y1, x2, y2]."""
    if not box_raw or len(box_raw) != 4:
        return None
    try:
        v1, v2, v3, v4 = [float(v) for v in box_raw]
    except (ValueError, TypeError):
        return None

    max_val = max(abs(v1), abs(v2), abs(v3), abs(v4))
    if max_val == 0:
        return None

    # Handle different coordinate scales
    if max_val <= 1.0:
        # Standard fractions (0.0 to 1.0)
        px1 = v1 * w
        py1 = v2 * h
        px2 = v3 * w
        py2 = v4 * h
    elif max_val <= 100.0 and (w >= 200 and h >= 200):
        # Percentage coordinates (0..100)
        px1 = (v1 / 100.0) * w
        py1 = (v2 / 100.0) * h
        px2 = (v3 / 100.0) * w
        py2 = (v4 / 100.0) * h
    elif max_val <= 1000.0:
        # Standard vision model normalized 0..1000 coordinates
        px1 = (v1 / 1000.0) * w
        py1 = (v2 / 1000.0) * h
        px2 = (v3 / 1000.0) * w
        py2 = (v4 / 1000.0) * h
    else:
        # Absolute pixel coordinates
        px1 = v1
        py1 = v2
        px2 = v3
        py2 = v4

    x1, x2 = sorted((max(0.0, min(float(w), px1)), max(0.0, min(float(w), px2))))
    y1, y2 = sorted((max(0.0, min(float(h), py1)), max(0.0, min(float(h), py2))))

    if (x2 - x1) < 2 and (y2 - y1) < 2:
        return None

    return [x1, y1, x2, y2]


def normalize_box_fractions(box_raw, w: int, h: int) -> list[float] | None:
    """Returns the normalized box as fractions [x1/w, y1/h, x2/w, y2/h] (0.0 to 1.0)."""
    pix = normalize_box(box_raw, w, h)
    if not pix or w <= 0 or h <= 0:
        return None
    return [pix[0] / w, pix[1] / h, pix[2] / w, pix[3] / h]


def draw_regions_png(image_bytes: bytes, regions: list[dict]) -> bytes:
    """Returns the marked image as PNG bytes with clear, vivid bounding boxes and labels."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size

    valid_boxes = []
    for i, region in enumerate(regions, start=1):
        box = normalize_box(region.get("box"), w, h)
        if not box:
            continue
        valid_boxes.append((i, region, box))

    if not valid_boxes:
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    # Prepare RGBA overlay for semi-transparent colored highlighting
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    thickness = max(3, round(min(w, h) * 0.006))
    badge_h = max(24, round(min(w, h) * 0.045))
    badge_w = max(32, round(badge_h * 1.3))

    try:
        font = ImageFont.load_default(size=max(12, round(badge_h * 0.6)))
    except Exception:
        font = ImageFont.load_default()

    # 1. Semi-transparent wash over each suspicious region
    for i, region, box in valid_boxes:
        is_sam = region.get("source") == "sam-3.1"
        fill_color = (20, 160, 60, 40) if is_sam else (220, 20, 20, 40)
        overlay_draw.rectangle(box, fill=fill_color)

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 2. High-contrast borders and number badges
    for i, region, box in valid_boxes:
        is_sam = region.get("source") == "sam-3.1"
        color = (20, 160, 60) if is_sam else (220, 20, 20)

        # Contrasting outer shadow/stroke
        draw.rectangle([box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1], outline=(0, 0, 0), width=thickness + 2)
        # Main colored border
        draw.rectangle(box, outline=color, width=thickness)

        # Badge positioning (above box if space allows, otherwise just inside top of box)
        if box[1] >= badge_h + 2:
            top = box[1] - badge_h
        else:
            top = box[1]
        badge_box = [box[0], top, box[0] + badge_w, top + badge_h]

        # Contrast outline and colored badge
        draw.rectangle([badge_box[0] - 1, badge_box[1] - 1, badge_box[2] + 1, badge_box[3] + 1], fill=(0, 0, 0))
        draw.rectangle(badge_box, fill=color)

        # Centered white number text
        text = str(i)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = badge_box[0] + (badge_w - tw) / 2
            ty = badge_box[1] + (badge_h - th) / 2 - 1
            draw.text((tx, ty), text, fill=(255, 255, 255), font=font)
        except Exception:
            draw.text((badge_box[0] + 8, badge_box[1] + 4), text, fill=(255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def draw_regions(image_bytes: bytes, regions: list[dict]) -> str:
    """Same, but returns a data URL for the web page."""
    png = draw_regions_png(image_bytes, regions)
    return "data:image/png;base64," + base64.b64encode(png).decode("utf-8")


def shrink_image(image_bytes: bytes, max_side: int = 1024, quality: int = 82) -> tuple[bytes, str]:
    """Telegram photos are big. Smaller images upload and process faster. Box positions are fractions, so they still match."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue(), "image/jpeg"

