"""Generate 25 synthetic evaluation screenshots and data/screens/labels.json for Phase B4."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SCREENS_DIR = ROOT / "data" / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_WIDTH, IMAGE_HEIGHT = 800, 450


def make_standard_scam(index: int):
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 62), fill="#17324d")
    draw.text((24, 24), "FICTIONAL ACCOUNT NOTICE", fill="white")
    draw.text((42, 105), "Please review this sample message.", fill="#222222")
    draw.text((42, 143), "This image contains no real message or account.", fill="#555555")
    x1 = 45 + (index * 47) % 440
    y1 = 220 + (index * 19) % 90
    x2, y2 = x1 + 250, y1 + 72
    draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill="#d92d20")
    draw.text((x1 + 82, y1 + 28), "Continue", fill="white")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "synthetic_standard"


def make_dark_mode_sms():
    # 15: Dark-mode SMS with a suspicious action link
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#121212")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 48), fill="#1e1e1e")
    draw.text((24, 16), "< Messages    +1 (800) 555-0199", fill="#e0e0e0")
    # SMS Bubble
    draw.rounded_rectangle((40, 80, 700, 240), radius=16, fill="#2c2c2e")
    draw.text((60, 100), "Postal Notice: Unpaid parcel handling fee of $2.40.", fill="#ffffff")
    draw.text((60, 130), "Confirm address to prevent package return.", fill="#ffffff")
    # Suspicious link button
    x1, y1, x2, y2 = 60, 170, 360, 215
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill="#0866ff")
    draw.text((x1 + 20, y1 + 14), "http://parcel-fee.example.org", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "link", False, "dark_mode_sms"


def make_cropped_email():
    # 16: Cropped email invoice
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#f8f9fa")
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, 780, 430), fill="#ffffff", outline="#e0e0e0")
    draw.text((40, 40), "From: billing@security-renewals-example.com", fill="#333333")
    draw.text((40, 70), "Subject: Invoice #94821 - Automatic Renewal Confirmation ($499.00)", fill="#111111")
    draw.line((40, 105, 760, 105), fill="#dddddd")
    draw.text((40, 125), "Your subscription has been renewed. To dispute this charge, click below:", fill="#444444")
    x1, y1, x2, y2 = 40, 180, 340, 240
    draw.rounded_rectangle((x1, y1, x2, y2), radius=6, fill="#c92a2a")
    draw.text((x1 + 40, y1 + 20), "Cancel Subscription", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "cropped_email"


def make_qr_code_page():
    # 17: Malicious QR-code pre-text page
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 50), fill="#212529")
    draw.text((24, 18), "SECURE TERMINAL VERIFICATION", fill="#ffffff")
    draw.text((40, 80), "Scan the security QR code with your mobile camera to authenticate:", fill="#212529")
    # Draw simulated QR box
    x1, y1, x2, y2 = 40, 130, 250, 340
    draw.rectangle((x1, y1, x2, y2), outline="#000000", width=4, fill="#ffffff")
    # Fake QR corner marks
    for cx, cy in [(x1 + 15, y1 + 15), (x2 - 55, y1 + 15), (x1 + 15, y2 - 55)]:
        draw.rectangle((cx, cy, cx + 40, cy + 40), fill="#000000")
        draw.rectangle((cx + 8, cy + 8, cx + 32, cy + 32), fill="#ffffff")
        draw.rectangle((cx + 14, cy + 14, cx + 26, cy + 26), fill="#000000")
    # Some mock QR noise
    for i in range(5):
        draw.rectangle((x1 + 75 + i * 18, y1 + 75 + i * 18, x1 + 88 + i * 18, y1 + 88 + i * 18), fill="#000000")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "qr code", False, "qr_page"


def make_tamil_scam():
    # 18: Tamil bank scam screenshot
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#f1f3f5")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 55), fill="#862e9c")
    draw.text((24, 20), "BANK SECURITY ALERT (TAMIL)", fill="#ffffff")
    draw.text((40, 90), "Account Suspended: Immediate Action Required", fill="#111111")
    draw.text((40, 130), "Unblock bank card and update KYC credentials online:", fill="#495057")
    x1, y1, x2, y2 = 40, 190, 320, 255
    draw.rounded_rectangle((x1, y1, x2, y2), radius=10, fill="#e03131")
    draw.text((x1 + 30, y1 + 22), "Unblock Account", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "tamil_scam"


def make_hindi_scam():
    # 19: Hindi lottery claim
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#fff9db")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 55), fill="#f59f00")
    draw.text((24, 20), "SPECIAL REWARD PORTAL", fill="#000000")
    draw.text((40, 90), "Congratulations! Cash Prize Allocation", fill="#111111")
    draw.text((40, 130), "Pay registration fee to unlock deposit directly into your account:", fill="#333333")
    x1, y1, x2, y2 = 40, 190, 330, 255
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill="#d9480f")
    draw.text((x1 + 35, y1 + 22), "Claim Prize Now", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "hindi_scam"


def make_bank_dialog_scam():
    # 20: Urgent modal dialog overlay
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#e9ecef")
    draw = ImageDraw.Draw(img)
    # Background blurred app
    draw.rectangle((0, 0, IMAGE_WIDTH, IMAGE_HEIGHT), fill="#6c757d")
    # Modal popup
    draw.rounded_rectangle((150, 60, 650, 380), radius=14, fill="#ffffff", outline="#343a40")
    draw.text((180, 90), "SECURITY WARNING: SUSPICIOUS ACTIVITY", fill="#c92a2a")
    draw.text((180, 140), "Your card was used in an unverified terminal.", fill="#212529")
    draw.text((180, 175), "Confirm your credentials immediately to avoid lock.", fill="#495057")
    x1, y1, x2, y2 = 180, 260, 480, 330
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill="#e03131")
    draw.text((x1 + 60, y1 + 24), "Verify My Identity", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "bank_dialog_scam"


def make_update_popup_scam():
    # 21: Fake software update
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#f8f9fa")
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 50, 700, 390), fill="#ffffff", outline="#adb5bd")
    draw.rectangle((100, 50, 700, 100), fill="#343a40")
    draw.text((120, 68), "Critical System Patch Required", fill="#ffffff")
    draw.text((120, 130), "Your browser security components are outdated.", fill="#212529")
    draw.text((120, 165), "Immediate installation is needed to prevent data exposure.", fill="#495057")
    x1, y1, x2, y2 = 120, 240, 420, 310
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill="#2b8a3e")
    draw.text((x1 + 40, y1 + 24), "Download Patch Now", fill="#ffffff")
    box = [round(x1 / IMAGE_WIDTH, 3), round(y1 / IMAGE_HEIGHT, 3), round(x2 / IMAGE_WIDTH, 3), round(y2 / IMAGE_HEIGHT, 3)]
    return img, [box], "button", False, "fake_update"


def make_safe_receipt():
    # 22: Safe bank transaction receipt (no scam boxes expected)
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 60), fill="#1971c2")
    draw.text((24, 22), "OFFICIAL TRANSACTION RECEIPT", fill="#ffffff")
    draw.text((40, 90), "Payment Successful to Corner Grocery Market", fill="#212529")
    draw.text((40, 130), "Amount: $24.80 | Date: Oct 27, 2026 | Ref: #REC-49102", fill="#495057")
    draw.line((40, 180, 760, 180), fill="#dee2e6")
    draw.text((40, 210), "Thank you for using your standard checking account.", fill="#6c757d")
    return img, [], "none", True, "safe_receipt"


def make_safe_school():
    # 23: Safe school calendar notice (no scam boxes expected)
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#f8f9fa")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 60), fill="#2f9e44")
    draw.text((24, 22), "GREENWOOD ELEMENTARY - WEEKLY BULLETIN", fill="#ffffff")
    draw.text((40, 90), "Parent-Teacher Conferences: November 12-14", fill="#212529")
    draw.text((40, 130), "Classrooms open from 3:30 PM to 6:00 PM. No appointment fee.", fill="#495057")
    draw.text((40, 170), "Snacks and refreshments will be provided in the cafeteria.", fill="#495057")
    return img, [], "none", True, "safe_school"


def make_safe_delivery():
    # 24: Safe official package delivered confirmation (no scam boxes expected)
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, IMAGE_WIDTH, 60), fill="#495057")
    draw.text((24, 22), "PACKAGE DELIVERED - METRO COURIER", fill="#ffffff")
    draw.text((40, 90), "Your package #EX-84920 has been safely delivered.", fill="#212529")
    draw.text((40, 130), "Left at: Front Porch behind flower pot.", fill="#495057")
    draw.text((40, 170), "No further action is required. Have a wonderful day!", fill="#6c757d")
    return img, [], "none", True, "safe_delivery"


def main():
    labels = {}
    generators = [
        *(lambda i=idx: make_standard_scam(i) for idx in range(15)),
        make_dark_mode_sms,
        make_cropped_email,
        make_qr_code_page,
        make_tamil_scam,
        make_hindi_scam,
        make_bank_dialog_scam,
        make_update_popup_scam,
        make_safe_receipt,
        make_safe_school,
        make_safe_delivery,
    ]

    for index, gen in enumerate(generators):
        img, boxes, concept, is_safe, screen_type = gen()
        fname = f"screen_{index:02d}.png"
        path = SCREENS_DIR / fname
        img.save(path, format="PNG")
        labels[fname] = {
            "index": index,
            "filename": fname,
            "expected_boxes": boxes,
            "concept": concept,
            "is_safe": is_safe,
            "type": screen_type,
            "synthetic": True,
        }
        print(f"Generated {fname}: is_safe={is_safe}, concept='{concept}', boxes={len(boxes)}")

    labels_file = SCREENS_DIR / "labels.json"
    labels_file.write_text(json.dumps(labels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote labels for {len(labels)} screens to {labels_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
