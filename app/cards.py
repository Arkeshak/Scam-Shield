"""Muse Image educational Real-vs-Scam comparison cards.
Docs: https://dev.meta.ai/docs/image-generation   (about $0.01 per image)"""
import base64
import io
import re

from PIL import Image, ImageDraw, ImageFont

from . import config
from .llm import get_client


# ── SCAM DOMAIN KNOWLEDGE BASE ────────────────────────────────────────────────
# Provides tailored, highly informative Real vs Scam educational guidance
# and specialized visual prompts for Meta Muse Image.

_KNOWLEDGE_BASE = {
    "bank": {
        "keywords": ["bank", "otp", "account", "transfer", "card", "credit", "fraud", "atm", "wire", "pay", "login", "auth", "suspended", "blocked"],
        "display": "Bank & Financial Alert",
        "left_art": "calm verified mobile banking notification card, green shield badge, secure padlock icon, soft emerald pastel theme, trustworthy official banking interface",
        "right_art": "fraudulent phishing SMS alert, crimson red danger accents, urgent dollar sign warning bubble, suspicious link symbol, exclamation mark hazard badge",
        "genuine": [
            "Official shortcode or verified app inbox",
            "Addresses you by name or masked account ID",
            "Never includes clickable login or OTP links",
            "Directs you to the official mobile app directly",
        ],
        "danger": [
            "Suspicious link to unverified clone site",
            "Asks for one-time code (OTP), PIN, or password",
            "Extreme urgency & threat of immediate suspension",
            "Sent from unknown mobile or international number",
        ],
        "golden_rule": "Legitimate banks NEVER ask for your OTP or password via SMS or phone. Never click links in unexpected security alerts.",
    },
    "delivery": {
        "keywords": ["delivery", "courier", "parcel", "package", "post", "shipping", "customs", "dhl", "fedex", "ups", "usps", "singpost", "tracking"],
        "display": "Parcel & Delivery Scam",
        "left_art": "official courier parcel tracking card, green checked parcel box icon, delivery status progress bar, soft green tones, authentic postal service",
        "right_art": "fake delivery failure alert, red warning symbols, urgent fee demand icons, suspicious link symbol, exclamation alarm bell",
        "genuine": [
            "Trackable directly on official courier website",
            "Includes specific tracking ID and merchant details",
            "No unexpected redelivery or customs fee demands",
            "Held at official depot or locker if delivery fails",
        ],
        "danger": [
            "Demands small payment ($1 - $5) to release package",
            "Shortened or misspelled web link (e.g., bit.ly)",
            "Vague notification without merchant or item details",
            "Requests full credit card info for 'rescheduling'",
        ],
        "golden_rule": "Always track parcels on the retailer's official app or tracking portal. Never pay delivery fees via unsolicited SMS links.",
    },
    "job": {
        "keywords": ["job", "task", "work", "career", "hiring", "commission", "part-time", "freelance", "salary", "earn", "daily income"],
        "display": "Job & Task Scam",
        "left_art": "official corporate career job offer letter, verified business badge, formal contract icon, calm emerald green theme",
        "right_art": "fraudulent instant task offer in messaging app, flying cash icons, urgent deposit requirement, crimson warning symbols",
        "genuine": [
            "Verified company domain and official recruiter email",
            "Formal interview and signed employment contract",
            "No upfront payments, deposits, or crypto needed",
            "Realistic compensation based on skills & hours",
        ],
        "danger": [
            "Unsolicited offer via WhatsApp, Telegram, or SMS",
            "Promises $300 - $1,000/day for simple 'review' tasks",
            "Requires paying deposit or topping up to 'unlock' pay",
            "Recruiter uses stolen corporate logos and urgent tone",
        ],
        "golden_rule": "Legitimate employers never require you to pay money or buy cryptocurrency in order to work for them.",
    },
    "investment": {
        "keywords": ["invest", "crypto", "bitcoin", "trading", "forex", "shares", "wealth", "fund", "returns", "profit", "guarantee"],
        "display": "Investment & Crypto Scheme",
        "left_art": "regulated financial investment app dashboard, verified securities shield, realistic market charts, calm green tones",
        "right_art": "fake get-rich-quick crypto platform, emergency countdown timer, 500% profit promise, crimson danger flags",
        "genuine": [
            "Licensed and listed on official regulator register",
            "Clear risk disclosures; investments can lose value",
            "Independent custody through regulated bank partners",
            "Transparent withdrawals without upfront 'unlock fees'",
        ],
        "danger": [
            "Promises 'guaranteed' high profit with zero risk",
            "Unregistered trading app or Telegram 'VIP' group",
            "High pressure to deposit more before allowing withdrawal",
            "Demands 'tax' or 'handling' fee before you can cash out",
        ],
        "golden_rule": "High returns with zero risk do not exist. Always verify investment firms on the official national regulatory register.",
    },
    "tech_support": {
        "keywords": ["tech support", "support", "virus", "microsoft", "apple", "windows", "hacked", "malware", "trojan", "anydesk", "teamviewer", "defender"],
        "display": "Tech Support Scam",
        "left_art": "official operating system security settings window, calm green check shield, automatic background scan icon",
        "right_art": "screaming browser lockup popup, fake virus alarm, urgent toll-free telephone number, flashing crimson red sirens",
        "genuine": [
            "Security scans run silently inside official OS settings",
            "Tech companies never cold-call about 'infected PCs'",
            "Official popups never include phone numbers to call",
            "Support is only initiated by you through official site",
        ],
        "danger": [
            "Loud browser popup claiming computer is locked",
            "Instructs you to call an urgent toll-free hotline",
            "Demands installation of remote access (AnyDesk/TeamViewer)",
            "Requests payment via gift cards, wire transfer, or crypto",
        ],
        "golden_rule": "Never call phone numbers displayed on browser popups or install remote access tools for unverified callers.",
    },
    "impersonation": {
        "keywords": ["mum", "dad", "family", "emergency", "lost phone", "relative", "friend", "hospital", "urgent help", "accident", "impersonat"],
        "display": "Family Impersonation Scam",
        "left_art": "verified family contact profile with profile photo, recognized phone number, heart icon, calm emerald green chat bubble",
        "right_art": "unknown number claiming to be family member in crisis, emergency hospital icon, urgent money transfer plea, crimson alert",
        "genuine": [
            "Reachable on their regular, known phone number",
            "Willing to talk via voice or live video call",
            "Knows personal family details only they would know",
            "No panic or insistence on secrecy from other relatives",
        ],
        "danger": [
            "'Hi Mum/Dad, I lost my phone, this is my new number'",
            "Urgent crisis story: hospital bill, unpaid rent, arrest",
            "Demands immediate money transfer to unfamiliar account",
            "Refuses voice or video calls due to 'broken microphone'",
        ],
        "golden_rule": "Always call your family member on their original saved phone number or verify through another relative before sending money.",
    },
    "government": {
        "keywords": ["police", "court", "tax", "irs", "customs", "immigration", "government", "arrest", "warrant", "fine", "officer", "ministry"],
        "display": "Government & Police Impersonation",
        "left_art": "official government letterhead with verified seal, formal postal mail, calm emerald green legal shield",
        "right_art": "fake arrest warrant image, WhatsApp call with stolen police badge photo, urgent fund transfer threat, crimson alert",
        "genuine": [
            "Official communications arrive via registered postal mail",
            "Officers never conduct interrogations via messaging apps",
            "Never asks citizens to transfer money to 'safe accounts'",
            "You have the right to visit the nearest station in person",
        ],
        "danger": [
            "Threatens immediate arrest, deportation, or asset freeze",
            "Calls via WhatsApp/Telegram displaying official crest",
            "Demands fund transfer to a 'safe verification account'",
            "Demands absolute secrecy: 'Do not tell your family'",
        ],
        "golden_rule": "Police and government agencies NEVER demand money transfers or threaten arrest over the phone. Hang up and verify in person.",
    },
    "prize": {
        "keywords": ["lottery", "prize", "reward", "gift", "won", "giveaway", "voucher", "selected", "contest", "spin", "lucky"],
        "display": "Prize & Lottery Scam",
        "left_art": "official store loyalty rewards card, verified gift certificate, calm emerald green gift ribbon",
        "right_art": "fake spinning prize wheel, claims of winning thousands, urgent processing fee demand, crimson exclamation marks",
        "genuine": [
            "You only win contests that you actually entered",
            "No upfront fee or tax needed to claim legitimate prizes",
            "Publicly verifiable winner lists from reputable brands",
            "Prizes delivered directly without pre-payment",
        ],
        "danger": [
            "Claims you won a lottery or sweepstakes you never entered",
            "Demands 'handling fee', 'customs fee', or bank details",
            "Artificial countdown timer claiming prize will expire soon",
            "Demands gift card codes to release the grand prize",
        ],
        "golden_rule": "If you have to pay money or provide financial details to claim a 'prize', it is guaranteed to be a scam.",
    },
}

_DEFAULT_CATEGORY = {
    "display": "Suspicious Scam",
    "left_art": "calm verified smartphone notification, green security shield badge, official sender icon, relaxed friendly design, soft green tones",
    "right_art": "fraudulent scam notification, crimson red warning symbol, suspicious urgent text bubble, dollar sign, alarm bell",
    "genuine": [
        "Verified sender email domain or official shortcode",
        "Calm, informative tone without artificial panic",
        "Points user to check account inside the official app",
        "Clear and accessible customer support contacts",
    ],
    "danger": [
        "Generic greeting (e.g., 'Dear Customer', 'Attention User')",
        "Extreme urgency or threats of immediate penalties",
        "Mismatched link pointing to unfamiliar web address",
        "Requests sensitive credentials, card numbers, or OTPs",
    ],
    "golden_rule": "When in doubt: pause, never tap links or share verification codes, and verify through official channels.",
}


def _get_category_info(scam_type: str, red_flags: list[str]) -> dict:
    """Find the best matching category from knowledge base using weighted scoring, or return default."""
    st_clean = scam_type.lower()
    flags_clean = " ".join(red_flags or []).lower()

    best_info = None
    best_score = 0

    for cat, info in _KNOWLEDGE_BASE.items():
        score = 0
        for kw in info["keywords"]:
            if kw in st_clean:
                score += 5  # Primary intent in scam type title
            elif kw in flags_clean:
                score += 2  # Match in detected red flags

        if score > best_score:
            best_score = score
            best_info = info

    return best_info or _DEFAULT_CATEGORY


def _font(size: int, bold: bool = False):
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]
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


def _wrap_text(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines = []
    cur = ""
    for word in words:
        test = f"{cur} {word}".strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ── PIL VECTOR DRAWING HELPERS ────────────────────────────────────────────────
# Guarantees crisp rendering across all OS fonts without broken unicode tofu (□).

def _draw_vector_check(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color=(255, 255, 255)):
    """Draw a clean vector checkmark centered at (cx, cy) with radius r."""
    p1 = (cx - r * 0.45, cy)
    p2 = (cx - r * 0.1, cy + r * 0.4)
    p3 = (cx + r * 0.45, cy - r * 0.35)
    w = max(2, int(r * 0.25))
    draw.line([p1, p2, p3], fill=color, width=w)


def _draw_vector_cross(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color=(255, 255, 255)):
    """Draw a clean vector 'X' cross centered at (cx, cy) with radius r."""
    delta = max(2, int(r * 0.42))
    w = max(2, int(r * 0.25))
    draw.line([(cx - delta, cy - delta), (cx + delta, cy + delta)], fill=color, width=w)
    draw.line([(cx - delta, cy + delta), (cx + delta, cy - delta)], fill=color, width=w)


def _draw_vector_shield(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill_col=(245, 158, 11)):
    """Draw a clean vector shield icon centered at (cx, cy) with radius r."""
    points = [
        (cx - int(r * 0.7), cy - int(r * 0.8)),
        (cx + int(r * 0.7), cy - int(r * 0.8)),
        (cx + int(r * 0.7), cy + int(r * 0.1)),
        (cx, cy + int(r * 0.9)),
        (cx - int(r * 0.7), cy + int(r * 0.1)),
    ]
    draw.polygon(points, fill=fill_col)


def make_comparison_card(scam_type: str, red_flags: list[str]) -> bytes | None:
    """Two-panel 'Real vs Scam' educational comparison card using Muse Image art + Pillow layout.

    Left panel: what a legitimate version looks like (calm, trusted, verified).
    Right panel: the hallmarks and red flags of this specific scam type.
    Returned as PNG bytes, or None on failure.
    """
    clean_type = scam_type.strip() if scam_type else "Scam Alert"
    category = _get_category_info(clean_type, red_flags or [])

    # Dynamic prompt for Muse Image
    muse_prompt = (
        "Modern 2D vector educational comparison infographic, split cleanly down the center by a subtle vertical line. "
        f"Left half (GENUINE / AUTHENTIC): {category['left_art']}. "
        f"Right half (FRAUD / SCAM): {category['right_art']}. "
        f"Minimalist flat UI mockup design, pastel colors, soft rounded corners, high contrast, clean vectors. "
        f"Context: {clean_type}. Absolutely NO text, NO letters, NO words, NO numbers, pure clean icons and shapes only."
    )

    try:
        response = get_client().images.generate(
            model=config.IMAGE_MODEL,
            prompt=muse_prompt,
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

    # ── overlay floating badges on the art ────────────────────────────────────
    adraw = ImageDraw.Draw(art)
    # Split divider through art
    adraw.line([(mid, 0), (mid, h)], fill=(255, 255, 255), width=max(2, int(w * 0.003)))

    pill_h = max(24, int(w * 0.046))
    pill_pad = int(w * 0.026)
    pill_font = _font(max(10, int(w * 0.021)), bold=True)

    # Left pill: GENUINE / SAFE
    l_text = "GENUINE / SAFE"
    l_bb = adraw.textbbox((0, 0), l_text, font=pill_font)
    l_w = (l_bb[2] - l_bb[0]) + int(pill_h * 1.5)
    adraw.rounded_rectangle(
        [pill_pad, pill_pad, pill_pad + l_w, pill_pad + pill_h],
        radius=pill_h // 2,
        fill=(16, 185, 129),
        outline=(255, 255, 255),
        width=max(1, int(w * 0.002)),
    )
    _draw_vector_check(adraw, pill_pad + pill_h // 2, pill_pad + pill_h // 2, pill_h // 3)
    adraw.text(
        (pill_pad + int(pill_h * 1.05), pill_pad + (pill_h - (l_bb[3] - l_bb[1])) // 2 - 1),
        l_text,
        fill=(255, 255, 255),
        font=pill_font,
    )

    # Right pill: SCAM / DANGER
    r_text = "SCAM / DANGER"
    r_bb = adraw.textbbox((0, 0), r_text, font=pill_font)
    r_w = (r_bb[2] - r_bb[0]) + int(pill_h * 1.5)
    r_x = w - pill_pad - r_w
    adraw.rounded_rectangle(
        [r_x, pill_pad, r_x + r_w, pill_pad + pill_h],
        radius=pill_h // 2,
        fill=(239, 68, 68),
        outline=(255, 255, 255),
        width=max(1, int(w * 0.002)),
    )
    _draw_vector_cross(adraw, r_x + pill_h // 2, pill_pad + pill_h // 2, pill_h // 3)
    adraw.text(
        (r_x + int(pill_h * 1.05), pill_pad + (pill_h - (r_bb[3] - r_bb[1])) // 2 - 1),
        r_text,
        fill=(255, 255, 255),
        font=pill_font,
    )

    # ── build informative content points ──────────────────────────────────────
    genuine_items = category["genuine"]

    # Combine detected red_flags with category danger points (with smart deduplication)
    stop_words = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "or", "and", "is", "it"}

    def _sig_tokens(text: str) -> set[str]:
        return {w for w in re.findall(r"\w+", text.lower()) if w not in stop_words}

    def _should_skip(toks: set[str], prev_toks: set[str]) -> bool:
        if toks.issubset(prev_toks) or prev_toks.issubset(toks):
            return True
        if len(toks & prev_toks) >= 2:
            return True
        return False

    danger_items = []
    seen_token_sets = []

    for flag in (red_flags or []):
        f = flag.strip()
        if f:
            toks = _sig_tokens(f)
            if not any(_should_skip(toks, prev) for prev in seen_token_sets):
                danger_items.append(f)
                seen_token_sets.append(toks)

    for item in category["danger"]:
        if len(danger_items) >= 4:
            break
        toks = _sig_tokens(item)
        if not any(_should_skip(toks, prev) for prev in seen_token_sets):
            danger_items.append(item)
            seen_token_sets.append(toks)

    golden_rule = category.get("golden_rule", _DEFAULT_CATEGORY["golden_rule"])

    # ── typography setup ──────────────────────────────────────────────────────
    title_font = _font(max(15, int(w * 0.034)), True)
    tag_font = _font(max(9, int(w * 0.017)), True)
    subtitle_font = _font(max(10, int(w * 0.020)), False)
    col_title_font = _font(max(11, int(w * 0.022)), True)
    item_font = _font(max(10, int(w * 0.019)), False)
    rule_title_font = _font(max(10, int(w * 0.020)), True)
    rule_body_font = _font(max(9, int(w * 0.018)), False)
    footer_font = _font(max(9, int(w * 0.017)), False)

    # Layout dimensions
    pad = int(w * 0.035)
    gap = int(w * 0.020)
    col_w = (w - pad * 2 - gap) // 2
    text_max_w = col_w - int(col_w * 0.22)

    # ── measure heights dynamically ───────────────────────────────────────────
    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)

    tag_text = "SCAMSHIELD SAFETY GUIDE"
    tag_bb = dd.textbbox((0, 0), tag_text, font=tag_font)
    tag_h = tag_bb[3] - tag_bb[1]

    title_text = f"REAL vs SCAM: {clean_type.upper()}"[:48]
    title_bb = dd.textbbox((0, 0), title_text, font=title_font)
    title_h = title_bb[3] - title_bb[1]

    sub_text = "Compare authentic communications with fraud attempts"
    sub_bb = dd.textbbox((0, 0), sub_text, font=subtitle_font)
    sub_h = sub_bb[3] - sub_bb[1]

    real_wrapped = [_wrap_text(it, item_font, text_max_w, dd) for it in genuine_items]
    scam_wrapped = [_wrap_text(it, item_font, text_max_w, dd) for it in danger_items]

    item_line_h = int(item_font.size * 1.35) if hasattr(item_font, "size") else 16
    bullet_gap = max(4, int(w * 0.012))

    real_col_h = sum(len(lines) * item_line_h + bullet_gap for lines in real_wrapped)
    scam_col_h = sum(len(lines) * item_line_h + bullet_gap for lines in scam_wrapped)
    cols_body_h = max(real_col_h, scam_col_h)
    col_header_h = max(24, int(w * 0.060))
    col_total_h = col_header_h + cols_body_h + int(pad * 0.5)

    rule_w = w - pad * 2
    rule_max_w = rule_w - int(w * 0.06)
    rule_wrapped = _wrap_text(golden_rule, rule_body_font, rule_max_w, dd)
    rule_line_h = int(rule_body_font.size * 1.35) if hasattr(rule_body_font, "size") else 14
    rule_h = int(rule_line_h * (len(rule_wrapped) + 1.2)) + int(pad * 0.6)

    footer_text = "ScamShield Family  |  Share with parents and family to keep them safe"
    footer_bb = dd.textbbox((0, 0), footer_text, font=footer_font)
    footer_h = footer_bb[3] - footer_bb[1]

    header_gap1 = max(8, int(w * 0.012))
    header_gap2 = max(14, int(w * 0.020))

    bar_h = pad + tag_h + header_gap1 + title_h + header_gap2 + sub_h + gap + col_total_h + gap + rule_h + gap + footer_h + pad

    # ── compose canvas ────────────────────────────────────────────────────────
    card = Image.new("RGB", (w, h + bar_h), (15, 23, 42))  # deep slate background
    card.paste(art, (0, 0))
    draw = ImageDraw.Draw(card)

    bar_top = h
    # Top accent bar below art
    draw.rectangle([0, bar_top, w, bar_top + max(2, int(w * 0.005))], fill=(59, 130, 246))

    # Header section
    y = bar_top + pad
    tag_w = tag_bb[2] - tag_bb[0]
    draw.text(((w - tag_w) // 2, y), tag_text, fill=(56, 189, 248), font=tag_font)
    y += tag_h + header_gap1

    title_w = title_bb[2] - title_bb[0]
    draw.text(((w - title_w) // 2, y), title_text, fill=(255, 255, 255), font=title_font)
    y += title_h + header_gap2

    sub_w = sub_bb[2] - sub_bb[0]
    draw.text(((w - sub_w) // 2, y), sub_text, fill=(148, 163, 184), font=subtitle_font)
    y += sub_h + gap

    # Comparison Columns
    col_top = y
    left_x = pad
    right_x = pad + col_w + gap

    # Left container: REAL / GENUINE
    draw.rounded_rectangle(
        [left_x, col_top, left_x + col_w, col_top + col_total_h],
        radius=10,
        fill=(6, 44, 30),
        outline=(16, 185, 129),
        width=1,
    )
    # Right container: SCAM / DANGER
    draw.rounded_rectangle(
        [right_x, col_top, right_x + col_w, col_top + col_total_h],
        radius=10,
        fill=(69, 10, 10),
        outline=(239, 68, 68),
        width=1,
    )

    # Column Headers
    ch_y = col_top + int(col_header_h * 0.22)
    _draw_vector_check(draw, left_x + int(col_w * 0.08), ch_y + 6, 7, color=(16, 185, 129))
    draw.text((left_x + int(col_w * 0.16), ch_y), "WHAT REAL LOOKS LIKE", fill=(167, 243, 208), font=col_title_font)

    _draw_vector_cross(draw, right_x + int(col_w * 0.08), ch_y + 6, 7, color=(239, 68, 68))
    draw.text((right_x + int(col_w * 0.16), ch_y), "SCAM WARNING SIGNS", fill=(254, 202, 202), font=col_title_font)

    # Inner horizontal divider lines below headers
    draw.line([(left_x + 8, col_top + col_header_h), (left_x + col_w - 8, col_top + col_header_h)], fill=(16, 185, 129, 90), width=1)
    draw.line([(right_x + 8, col_top + col_header_h), (right_x + col_w - 8, col_top + col_header_h)], fill=(239, 68, 68, 90), width=1)

    # Bullet lists
    icon_r = max(5, int(w * 0.011))

    # Left bullets (Genuine)
    by = col_top + col_header_h + int(pad * 0.4)
    for lines in real_wrapped:
        _draw_vector_check(draw, left_x + int(col_w * 0.08), by + item_line_h // 2, icon_r, color=(52, 211, 153))
        text_x = left_x + int(col_w * 0.16)
        ty = by
        for line in lines:
            draw.text((text_x, ty), line, fill=(240, 253, 244), font=item_font)
            ty += item_line_h
        by = ty + bullet_gap

    # Right bullets (Scam)
    by = col_top + col_header_h + int(pad * 0.4)
    for lines in scam_wrapped:
        _draw_vector_cross(draw, right_x + int(col_w * 0.08), by + item_line_h // 2, icon_r, color=(248, 113, 113))
        text_x = right_x + int(col_w * 0.16)
        ty = by
        for line in lines:
            draw.text((text_x, ty), line, fill=(254, 242, 242), font=item_font)
            ty += item_line_h
        by = ty + bullet_gap

    y = col_top + col_total_h + gap

    # Golden Rule box
    draw.rounded_rectangle([pad, y, pad + rule_w, y + rule_h], radius=8, fill=(30, 41, 59), outline=(245, 158, 11), width=1)
    draw.rounded_rectangle([pad, y, pad + 4, y + rule_h], radius=2, fill=(245, 158, 11))

    ry = y + int(pad * 0.3)
    rx = pad + int(w * 0.03)
    shield_r = max(5, int(w * 0.010))
    _draw_vector_shield(draw, rx + shield_r, ry + int(rule_title_font.size * 0.45), shield_r, fill_col=(245, 158, 11))
    draw.text((rx + int(shield_r * 2.4), ry), "FAMILY GOLDEN RULE", fill=(251, 191, 36), font=rule_title_font)
    ry += int(rule_line_h * 1.1)
    for line in rule_wrapped:
        draw.text((rx, ry), line, fill=(241, 245, 249), font=rule_body_font)
        ry += rule_line_h

    y += rule_h + gap

    # Footer
    footer_w = footer_bb[2] - footer_bb[0]
    draw.text(((w - footer_w) // 2, y), footer_text, fill=(148, 163, 184), font=footer_font)

    out = io.BytesIO()
    card.save(out, format="PNG")
    return out.getvalue()
