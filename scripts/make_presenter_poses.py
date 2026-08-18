"""Generate the two presenter worm placeholder poses."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
from PIL import Image, ImageDraw, ImageFont

def load_font(size):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

def make_presenter(filename, pointing_right: bool):
    os.makedirs("assets/worm", exist_ok=True)
    W, H = 260, 340
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # body
    d.ellipse([(40, 160), (220, 320)], fill=(255, 210, 50))
    # head
    d.ellipse([(40, 40), (220, 220)], fill=(255, 210, 50))
    # eyes
    for ex in (100, 160):
        d.ellipse([(ex - 12, 110), (ex + 12, 140)], fill="white")
        d.ellipse([(ex - 6, 116), (ex + 6, 134)], fill=(30, 30, 30))
    # smile
    d.arc([(90, 145), (170, 185)], start=0, end=180, fill=(80, 40, 0), width=4)
    # hat
    d.rectangle([(95, 0), (165, 50)], fill=(20, 20, 20))
    d.rectangle([(75, 48), (185, 58)], fill=(20, 20, 20))
    # arm + arrow
    if pointing_right:
        d.line([(180, 180), (245, 145)], fill=(200, 140, 0), width=7)
        d.polygon([(245, 145), (228, 132), (255, 127)], fill=(200, 140, 0))
    else:
        d.line([(80, 180), (15, 145)], fill=(200, 140, 0), width=7)
        d.polygon([(15, 145), (32, 132), (5, 127)], fill=(200, 140, 0))
    # label
    font_s = load_font(18)
    label = "pres-right" if pointing_right else "pres-left"
    d.text((5, H - 24), label, font=font_s, fill=(100, 100, 100))

    path = f"assets/worm/{filename}"
    img.save(path)
    print(f"  Created {path}")

make_presenter("presenter_pointing-the-left.png",  pointing_right=False)
make_presenter("presenter_pointing-the-right.png", pointing_right=True)
print("Done.")
