"""Muse Image educational Real-vs-Scam comparison cards.
Docs: https://dev.meta.ai/docs/image-generation   (about $0.01 per image)"""
import base64
import io

from PIL import Image, ImageDraw, ImageFont

from . import config
from .llm import get_client


def _font(size: int, bold: bool = False):
    candidates = (
        ["arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def make_comparison_card(scam_type: str, red_flags: list[str]) -> bytes | None:
    """Two-panel 'Real vs Scam' educational card using Muse Image art + Pillow labels.

    Left panel: what a legitimate version looks like (calm, trusted).
    Right panel: the hallmarks of this specific scam type.
    Returned as PNG bytes, or None on failure.
    """
    try:
        response = get_client().images.generate(
            model=config.IMAGE_MODEL,
            prompt=(
                "Flat educational split illustration, divided exactly down the middle by a thin vertical line. "
                "Left half: a calm, clean, trustworthy smartphone notification — green checkmark badge, "
                "official sender icon, relaxed friendly design, soft green tones. "
                f"Right half: the same type of notification but as a scam — red warning symbol, "
                f"suspicious urgent text bubble, dollar sign, exclamation marks, alarm bell, Theme: {scam_type}. "
                "No text, no letters, no numbers. Minimal, friendly, clear."
            ),
            n=1,
            extra_body={
                "reasoning_strength": "low",
                "tool_enablement": {"enable_web_search": False, "enable_shell": False, "enable_image_search": False},
                "output_format": "png",
            },
        )
        art = Image.open(io.BytesIO(base64.b64decode(response.data[0].b64_json))).convert("RGB")
    except Exception as e:
        print(f"[cards] comparison card image generation failed: {e}")
        return None

    w, h = art.size
    mid = w // 2

    title_font = _font(max(18, int(w * 0.038)), True)
    label_font = _font(max(22, int(w * 0.046)), True)
    flag_font = _font(max(14, int(w * 0.026)))
    footer_font = _font(max(11, int(w * 0.018)))

    # ── measure text for bar sizing ──────────────────────────────────────────
    dummy = Image.new("RGB", (1, 1))
    d = ImageDraw.Draw(dummy)

    title_text = f"REAL vs SCAM: {scam_type.upper()}"[:50]
    title_bb = d.textbbox((0, 0), title_text, font=title_font)
    title_h = title_bb[3] - title_bb[1]

    label_bb = d.textbbox((0, 0), "✓ REAL", font=label_font)
    label_h = label_bb[3] - label_bb[1]

    # Wrap red flags to fit left or right half (minus margins)
    half_w = mid - int(w * 0.06)
    flag_lines: list[str] = []
    for flag in (red_flags or ["Pressure tactics", "Urgency", "Asks for money"])[:4]:
        words = flag.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            bb = d.textbbox((0, 0), f"• {test}", font=flag_font)
            if bb[2] - bb[0] <= half_w:
                line = test
            else:
                if line:
                    flag_lines.append(line)
                line = word
        if line:
            flag_lines.append(line)

    line_h = int(flag_font.size * 1.4) if hasattr(flag_font, "size") else 28
    flags_total_h = len(flag_lines) * line_h

    footer_text = "ScamShield Family  |  Learn to spot the difference"
    footer_bb = d.textbbox((0, 0), footer_text, font=footer_font)
    footer_w, footer_h = footer_bb[2] - footer_bb[0], footer_bb[3] - footer_bb[1]

    pad = int(w * 0.04)
    gap = int(w * 0.016)
    content_h = title_h + gap + label_h + gap + flags_total_h + gap * 2 + footer_h
    bar_h = max(int(h * 0.36), content_h + pad * 2)

    # ── compose canvas ────────────────────────────────────────────────────────
    card = Image.new("RGB", (w, h + bar_h), (255, 255, 255))
    card.paste(art, (0, 0))
    draw = ImageDraw.Draw(card)

    # Divider line through the art
    draw.line([(mid, 0), (mid, h)], fill=(255, 255, 255), width=3)

    # Bottom bar: left (green) + right (red)
    bar_top = h
    draw.rectangle([0, bar_top, mid, bar_top + bar_h], fill=(20, 83, 45))     # dark green
    draw.rectangle([mid, bar_top, w, bar_top + bar_h], fill=(127, 29, 29))    # dark red
    # Divider in bar
    draw.line([(mid, bar_top), (mid, bar_top + bar_h)], fill=(255, 255, 255), width=2)
    # Top accent line
    draw.line([(0, bar_top), (w, bar_top)], fill=(74, 222, 128), width=2)

    # ── title (centered across full width) ───────────────────────────────────
    y = bar_top + pad
    title_w_px = title_bb[2] - title_bb[0]
    draw.text(((w - title_w_px) // 2, y), title_text, fill=(255, 255, 255), font=title_font)
    y += title_h + gap

    # ── left label: ✓ REAL ───────────────────────────────────────────────────
    real_label = "✓ REAL"
    real_bb = d.textbbox((0, 0), real_label, font=label_font)
    real_w = real_bb[2] - real_bb[0]
    draw.text(((mid - real_w) // 2, y), real_label, fill=(134, 239, 172), font=label_font)

    # ── right label: ✗ SCAM ──────────────────────────────────────────────────
    scam_label = "✗ SCAM"
    scam_bb = d.textbbox((0, 0), scam_label, font=label_font)
    scam_w = scam_bb[2] - scam_bb[0]
    draw.text((mid + (mid - scam_w) // 2, y), scam_label, fill=(252, 165, 165), font=label_font)
    y += label_h + gap

    # ── right panel: red flags list ───────────────────────────────────────────
    flag_x = mid + int(w * 0.03)
    for line in flag_lines:
        draw.text((flag_x, y), f"• {line}", fill=(254, 226, 226), font=flag_font)
        y += line_h

    # ── left panel: safe behaviours ──────────────────────────────────────────
    safe_lines = ["Official sender ID", "No urgency or threats", "Never asks for codes"]
    sy = bar_top + pad + title_h + gap + label_h + gap
    safe_x = int(w * 0.03)
    for sl in safe_lines:
        draw.text((safe_x, sy), f"✓ {sl}", fill=(187, 247, 208), font=flag_font)
        sy += line_h

    # ── footer ────────────────────────────────────────────────────────────────
    footer_y = bar_top + bar_h - pad - footer_h
    draw.text(((w - footer_w) // 2, footer_y), footer_text, fill=(203, 213, 225), font=footer_font)

    out = io.BytesIO()
    card.save(out, format="PNG")
    return out.getvalue()
