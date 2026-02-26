from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def ar(text):
    return get_display(arabic_reshaper.reshape(text))

def make_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

arial   = "C:/Windows/Fonts/arial.ttf"
arialbd = "C:/Windows/Fonts/arialbd.ttf"

ICON_PATH = "static/images/inify-icon.png"

def paste_logo(img, x, y, size=140):
    icon = Image.open(ICON_PATH).convert("RGBA")
    icon = icon.resize((size, size), Image.LANCZOS)
    img.paste(icon, (x, y), icon)

def draw_base(W=1200, H=630):
    img = Image.new("RGB", (W, H), "#0D1B2A")
    draw = ImageDraw.Draw(img)
    for i in range(H):
        ratio = i / H
        r = int(13 + (28 - 13) * ratio)
        g = int(27 + (50 - 27) * ratio)
        b = int(42 + (80 - 42) * ratio)
        draw.line([(0, i), (W, i)], fill=(r, g, b))
    for rad in [280, 220, 160]:
        draw.ellipse([W-60-rad, H//2-rad, W-60+rad, H//2+rad],
                     outline=(107, 184, 201), width=1)
    return img, draw

f72 = make_font(arialbd, 72)
f42 = make_font(arialbd, 42)
f30 = make_font(arial,   30)
f26 = make_font(arial,   26)

# ── صورة 1: inify-og.png (الشركة العامة) ──
img, draw = draw_base()
# لوجو في أعلى اليسار
paste_logo(img, 80, 60, size=130)
draw.text((230, 80),  "inify",                        font=f72, fill=(255,255,255))
draw.text((230, 170), "AI Solutions for Business",    font=f30, fill=(107,184,201))
draw.line([(80,248),(700,248)], fill=(107,184,201), width=1)
draw.text((80, 268), ar("شركة ذكاء اصطناعي سعودية"),          font=f42, fill=(255,255,255))
draw.text((80, 330), ar("حلول AI متقدمة للأعمال والمؤسسات"),   font=f30, fill=(200,220,235))
badges = ["وكلاء ذكية", "أتمتة الأعمال", "تكامل أنظمة"]
bx = 80
for badge in badges:
    draw.rounded_rectangle([bx, 400, bx+200, 448], radius=22, fill=(26,43,69))
    draw.rounded_rectangle([bx, 400, bx+200, 448], radius=22, outline=(107,184,201), width=1)
    draw.text((bx+15, 413), ar(badge), font=f26, fill=(107,184,201))
    bx += 220
draw.text((80, 490), "inify.ai", font=f30, fill=(107,184,201))
img.save("static/images/inify-og.png", "PNG", optimize=True)
print("Created: static/images/inify-og.png")

# ── صورة 2: inify-og-estate.png (المنتج العقاري) ──
img2, draw2 = draw_base()
paste_logo(img2, 80, 60, size=130)
draw2.text((230, 80),  "inify",                       font=f72, fill=(255,255,255))
draw2.text((230, 170), "AI Solutions for Business",   font=f30, fill=(107,184,201))
draw2.line([(80,248),(700,248)], fill=(107,184,201), width=1)
draw2.text((80, 268), ar("أول وكيل عقاري ذكي في السعودية"),            font=f42, fill=(255,255,255))
draw2.text((80, 330), ar("وكيل ذكاء اصطناعي يدير مبيعاتك العقارية تلقائياً 24/7"), font=f26, fill=(200,220,235))
draw2.rounded_rectangle([80, 400, 360, 448], radius=22, fill=(107,184,201))
draw2.text((100, 413), ar("تجربة مجانية 5 أيام"), font=f26, fill=(13,27,42))
draw2.text((80, 490), "inify.ai/estate/", font=f30, fill=(107,184,201))
img2.save("static/images/inify-og-estate.png", "PNG", optimize=True)
print("Created: static/images/inify-og-estate.png")
