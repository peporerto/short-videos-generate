"""
scripts/generate_differences_assets.py
--------------------------------------
Generates placeholder assets for the `differences` niche so the pipeline
can run a test render before real artwork is supplied.

Placeholders created:
  assets/worm/presenter.png   — yellow worm with top hat
  assets/worm/confused.png    — yellow worm with question marks
  assets/worm/professor.png   — yellow worm with glasses
  assets/differences/background.gif — crumpled paper texture
  input/differences/script.txt — sample diff1 script
  input/differences/diff1/imageA.png — blue square (desert)
  input/differences/diff1/imageB.png — red square (dessert)
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

def load_font(size):
    for path in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ── 1. Worm placeholders ───────────────────────────────────────────────────────

def make_worm(filename, label, hat=False, glasses=False, question=False):
    os.makedirs("assets/worm", exist_ok=True)
    W, H = 260, 340
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Body — rounded yellow oval
    body_x0, body_y0, body_x1, body_y1 = 40, 160, 220, 320
    d.ellipse([(body_x0, body_y0), (body_x1, body_y1)], fill=(255, 210, 50))

    # Head — larger circle
    head_cx, head_cy, head_r = 130, 130, 90
    d.ellipse(
        [(head_cx - head_r, head_cy - head_r), (head_cx + head_r, head_cy + head_r)],
        fill=(255, 210, 50),
    )

    # Eyes
    for ex in (100, 160):
        d.ellipse([(ex - 12, head_cy - 20), (ex + 12, head_cy + 10)], fill="white")
        d.ellipse([(ex - 6, head_cy - 14), (ex + 6, head_cy + 4)], fill=(30, 30, 30))

    # Smile
    d.arc([(90, head_cy + 5), (170, head_cy + 45)], start=0, end=180, fill=(80, 40, 0), width=4)

    if hat:
        # Top hat — black rectangle + brim
        d.rectangle([(95, 0), (165, 50)], fill=(20, 20, 20))
        d.rectangle([(75, 48), (185, 58)], fill=(20, 20, 20))

    if glasses:
        for gx in (95, 135):
            d.ellipse([(gx, head_cy - 25), (gx + 35, head_cy + 5)], outline=(50, 50, 50), width=3)

    if question:
        font = load_font(40)
        d.text((190, 20), "?", font=font, fill=(255, 80, 0))
        d.text((55, 30), "?", font=font, fill=(255, 80, 0))

    # Label (tiny, for debugging)
    font_s = load_font(18)
    d.text((5, H - 24), label, font=font_s, fill=(100, 100, 100))

    img.save(f"assets/worm/{filename}")
    print(f"  Created assets/worm/{filename}")


make_worm("presenter.png", "presenter", hat=True)
make_worm("confused.png",  "confused",  question=True)
make_worm("professor.png", "professor", glasses=True)


# ── 2. Background — crumpled paper texture ─────────────────────────────────────

import random

def make_background():
    os.makedirs("assets/differences", exist_ok=True)
    W, H = 720, 1280
    rng = random.Random(42)

    img = Image.new("RGB", (W, H), (245, 240, 230))
    d = ImageDraw.Draw(img)

    # Simulate crumpled paper with random short light/dark lines
    for _ in range(1800):
        x1 = rng.randint(0, W)
        y1 = rng.randint(0, H)
        length = rng.randint(8, 60)
        angle_x = rng.randint(-30, 30)
        angle_y = rng.randint(-8, 8)
        brightness = rng.randint(-15, 15)
        base = 230
        color = (
            max(180, min(255, base + brightness)),
            max(180, min(255, base + brightness - 2)),
            max(160, min(245, base + brightness - 8)),
        )
        d.line([(x1, y1), (x1 + angle_x, y1 + angle_y + length)], fill=color, width=rng.randint(1, 2))

    # Slight vignette
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for r in range(min(W, H) // 2, 0, -8):
        alpha = max(0, int((1.0 - r / (min(W, H) / 2)) * 40))
        vd.ellipse([(W // 2 - r, H // 2 - r), (W // 2 + r, H // 2 + r)], outline=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

    img.save("assets/differences/background.gif")
    print("  Created assets/differences/background.gif")


make_background()


# ── 3. Sample input images ─────────────────────────────────────────────────────

def make_sample_image(path, label, bg_color, text_color=(255, 255, 255)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    W, H = 600, 450
    img = Image.new("RGB", (W, H), bg_color)
    d = ImageDraw.Draw(img)
    font = load_font(54)
    font_s = load_font(28)
    # Centred label
    bbox = font.getbbox(label)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text(((W - tw) // 2, (H - th) // 2 - 20), label, font=font, fill=text_color)
    sub = "(placeholder)"
    bb2 = font_s.getbbox(sub)
    d.text(((W - (bb2[2] - bb2[0])) // 2, (H + th) // 2 + 5), sub, font=font_s, fill=(*text_color[:3],))
    img.save(path)
    print(f"  Created {path}")


make_sample_image(
    "input/differences/diff1/imageA.png",
    "DESERT",
    (210, 170, 90),
    (80, 50, 10),
)
make_sample_image(
    "input/differences/diff1/imageB.png",
    "DESSERT",
    (180, 80, 120),
    (255, 240, 240),
)


# ── 4. Sample script ───────────────────────────────────────────────────────────

script = """\
diff1:
Desert vs Dessert — do you know the difference?
What's the difference?
A desert is a dry, barren landscape that receives very little rainfall.
A dessert is a sweet course eaten at the end of a meal. Don't mix them up!
"""

os.makedirs("input/differences", exist_ok=True)
with open("input/differences/script.txt", "w", encoding="utf-8") as f:
    f.write(script)
print("  Created input/differences/script.txt")

print("\nAll placeholder assets generated successfully.")
