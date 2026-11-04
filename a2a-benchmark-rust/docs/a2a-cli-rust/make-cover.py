#!/usr/bin/env python3
"""Textless cover: a terminal prompt fanning out to three agents.
Blue path straight to a node, orange through a wrapper box, grey through a
cloud (the model) first. 1376x578 (dev.to's 2.381:1 display), content-addressed."""
import hashlib, math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W, H, S = 1376, 578, 2
BG, INK = (28, 28, 30), (236, 234, 226)
BLUE, ORANGE, GREY = (66, 140, 255), (236, 104, 44), (150, 150, 146)
img = Image.new("RGB", (W * S, H * S), BG)
glow = Image.new("RGB", img.size, (0, 0, 0))
d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)

def P(x, y): return (x * S, y * S)

def bez(p0, p1, p2, p3, n=200):
    return [tuple(((1-t)**3)*a + 3*((1-t)**2)*t*b + 3*(1-t)*t*t*c + t**3*e
                  for a, b, c, e in zip(p0, p1, p2, p3)) for t in (i / n for i in range(n + 1))]

def line(pts, col, w):
    pts = [P(*p) for p in pts]
    for k in range(-2, 3):
        d.line([(x, y + k * 3) for x, y in pts], fill=tuple(int(c * (0.55 + 0.1 * (2 - abs(k)))) for c in col), width=w)
    g.line(pts, fill=col, width=w * 6)

def gear(cx, cy, r, col):
    teeth = 8
    pts = []
    for i in range(teeth * 2):
        a = math.pi * i / teeth
        rr = r if i % 2 == 0 else r * 0.78
        for j in (-0.18, 0.18):
            pts.append(P(cx + rr * math.cos(a + j), cy + rr * math.sin(a + j)))
    d.polygon(pts, outline=col, width=5 * S)
    g.polygon(pts, fill=col)
    d.ellipse([*P(cx - r * .3, cy - r * .3), *P(cx + r * .3, cy + r * .3)], fill=col)

# terminal source
tx, ty = 170, 289
d.rounded_rectangle([*P(tx - 85, ty - 62), *P(tx + 85, ty + 62)], radius=14 * S, fill=(44, 44, 48), outline=INK, width=4 * S)
g.rounded_rectangle([*P(tx - 85, ty - 62), *P(tx + 85, ty + 62)], radius=14 * S, fill=(90, 90, 90))
d.line([P(tx - 45, ty - 22), P(tx - 15, ty), P(tx - 45, ty + 22)], fill=INK, width=7 * S, joint="curve")
d.line([P(tx + 2, ty + 24), P(tx + 42, ty + 24)], fill=ORANGE, width=7 * S)

start, nx = (tx + 90, ty), 1120
ys = (120, 289, 458)
line(bez(start, (520, ty), (560, ys[0]), (nx - 60, ys[0])), BLUE, 3 * S)
line(bez(start, (520, ty), (600, ys[1]), (nx - 60, ys[1])), ORANGE, 3 * S)
line(bez(start, (520, ty), (560, ys[2]), (nx - 60, ys[2])), GREY, 3 * S)
# wrapper box on the orange path, cloud on the grey path
bx = 760
d.rectangle([*P(bx - 48, ys[1] - 40), *P(bx + 48, ys[1] + 40)], fill=BG, outline=ORANGE, width=4 * S)
d.line([P(bx - 48, ys[1] - 18), P(bx + 48, ys[1] - 18)], fill=ORANGE, width=3 * S)
cx = 770
for ox, oy, r in ((-34, 8, 30), (0, -12, 40), (36, 6, 32), (0, 18, 30)):
    g.ellipse([*P(cx + ox - r, ys[2] + oy - r), *P(cx + ox + r, ys[2] + oy + r)], fill=(70, 70, 68))
    d.ellipse([*P(cx + ox - r, ys[2] + oy - r), *P(cx + ox + r, ys[2] + oy + r)], fill=(58, 58, 60))
for col, y in zip((BLUE, ORANGE, GREY), ys):
    gear(nx + 30, y, 58, (183, 65, 14) if col is not GREY else (183, 65, 14))
    d.ellipse([*P(nx + 30 - 70, y - 70), *P(nx + 30 + 70, y + 70)], outline=col, width=3 * S)

glow = glow.filter(ImageFilter.GaussianBlur(28 * S))
out = Image.blend(img, Image.composite(glow, img, glow.convert("L")), 0.0)
out = Image.eval(Image.merge("RGB", [Image.eval(a, lambda v: v) for a in img.split()]), lambda v: v)
final = Image.new("RGB", img.size)
final.paste(Image.composite(img, img, img.convert("L")))
from PIL import ImageChops
final = ImageChops.add(img, ImageChops.multiply(glow, Image.new("RGB", img.size, (110, 110, 110))))
final = final.resize((W, H), Image.LANCZOS)
here = Path(__file__).parent
tmp = here / "devto-cover.tmp.jpg"
final.save(tmp, quality=92)
h = hashlib.sha256(tmp.read_bytes()).hexdigest()[:8]
dst = here / f"devto-cover.{h}.jpg"
tmp.rename(dst)
print(dst.name, f"{W}x{H}", f"{dst.stat().st_size // 1024} KB")
