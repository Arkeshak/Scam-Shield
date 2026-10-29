"""Generate a fictional, non-personal scam-message screenshot for demos."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "demo_screenshot.png"
WIDTH, HEIGHT = 900, 600


def font(size):
    for candidate in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    image = Image.new("RGB", (WIDTH, HEIGHT), "#edf1f7")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((38, 28, 862, 572), radius=28, fill="#ffffff", outline="#d5dce8", width=3)
    draw.rectangle((38, 28, 862, 112), fill="#15304b")
    draw.text((76, 52), "FICTIONAL PRIZE MESSAGE - DEMO ONLY", font=font(27), fill="#ffffff")
    draw.text((84, 150), "CONGRATULATIONS! YOU WON $5,000", font=font(29), fill="#1d2939")
    draw.text((84, 208), "Pay a $20 fee today to claim your prize.", font=font(27), fill="#b42318")
    draw.text((84, 267), "You did not enter? Claim before time runs out!", font=font(23), fill="#344054")
    draw.text((84, 323), "https://prize-claim.example.invalid", font=font(22), fill="#b42318")
    draw.rounded_rectangle((84, 390, 816, 484), radius=15, fill="#d92d20")
    draw.text((334, 420), "CLAIM PRIZE", font=font(30), fill="#ffffff")
    draw.text((84, 520), "Synthetic example. No real person, company, link, or prize.", font=font(19), fill="#667085")
    image.save(OUTPUT, format="PNG", optimize=True)
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
