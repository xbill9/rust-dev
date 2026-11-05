#!/usr/bin/env python3
"""Textless cover: one terminal prompt, the same two agents twice.

Left of the terminal the laptop pair, right of it the same pair inside a cloud.
Blue square = the Rust agent, orange circle = the Strands coordinator; the
coordinator reaches its Rust agent through a second, smaller prompt. 1376x578
(dev.to's 2.381:1 display), content-addressed."""
import hashlib
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, S = 1376, 578, 2
BG, INK, PANEL = (28, 28, 30), (236, 234, 226), (44, 44, 48)
BLUE, ORANGE, CLOUD = (66, 140, 255), (236, 104, 44), (54, 56, 62)
img = Image.new("RGB", (W * S, H * S), BG)
glow = Image.new("RGB", img.size, (0, 0, 0))
d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)


def P(x, y):
    return (x * S, y * S)


def bez(p0, p1, p2, p3, n=200):
    return [tuple(((1 - t) ** 3) * a + 3 * ((1 - t) ** 2) * t * b + 3 * (1 - t) * t * t * c + t ** 3 * e
                  for a, b, c, e in zip(p0, p1, p2, p3)) for t in (i / n for i in range(n + 1))]


def line(pts, col, w=3):
    pts = [P(*p) for p in pts]
    d.line(pts, fill=tuple(int(c * 0.75) for c in col), width=w * S)
    g.line(pts, fill=col, width=w * 6 * S)


def terminal(x, y, w, h, cursor):
    d.rounded_rectangle([*P(x - w, y - h), *P(x + w, y + h)], radius=14 * S, fill=PANEL, outline=INK, width=4 * S)
    g.rounded_rectangle([*P(x - w, y - h), *P(x + w, y + h)], radius=14 * S, fill=(90, 90, 90))
    k = h / 62
    d.line([P(x - 45 * k, y - 22 * k), P(x - 15 * k, y), P(x - 45 * k, y + 22 * k)], fill=INK, width=int(7 * k) * S, joint="curve")
    d.line([P(x + 2 * k, y + 24 * k), P(x + 42 * k, y + 24 * k)], fill=cursor, width=int(7 * k) * S)


def rust(x, y):
    d.rounded_rectangle([*P(x - 44, y - 44), *P(x + 44, y + 44)], radius=8 * S, fill=BG, outline=BLUE, width=5 * S)
    g.rounded_rectangle([*P(x - 44, y - 44), *P(x + 44, y + 44)], radius=8 * S, fill=BLUE)
    d.rectangle([*P(x - 14, y - 14), *P(x + 14, y + 14)], fill=BLUE)


def strands(x, y):
    d.ellipse([*P(x - 46, y - 46), *P(x + 46, y + 46)], fill=BG, outline=ORANGE, width=5 * S)
    g.ellipse([*P(x - 46, y - 46), *P(x + 46, y + 46)], fill=ORANGE)
    d.ellipse([*P(x - 15, y - 15), *P(x + 15, y + 15)], fill=ORANGE)


# the cloud behind the right-hand pair
for ox, oy, r in ((1090, 290, 165), (1210, 240, 135), (1270, 350, 110), (990, 365, 110), (1150, 395, 140)):
    d.ellipse([*P(ox - r, oy - r), *P(ox + r, oy + r)], fill=CLOUD)

tx, ty = 688, 289
terminal(tx, ty, 85, 62, ORANGE)
pairs = ((300, 170, 300, 420), (1110, 170, 1110, 420))  # (strands x, y, rust x, y)
for sx, sy, rx, ry in pairs:
    side = -1 if sx < tx else 1
    start = (tx + side * 90, ty)
    line(bez(start, (tx + side * 200, ty), (sx - side * 200, sy), (sx - side * 52, sy)), ORANGE)
    line(bez(start, (tx + side * 200, ty), (rx - side * 200, ry), (rx - side * 50, ry)), BLUE)
    # the coordinator's own small prompt, on the way down to its Rust agent
    mx, my = sx + side * 120, (sy + ry) / 2
    line([(sx + side * 30, sy + 36), (mx, my - 24)], ORANGE, 2)
    line([(mx, my + 24), (rx + side * 30, ry - 36)], BLUE, 2)
    terminal(mx, my, 34, 25, BLUE)
    strands(sx, sy)
    rust(rx, ry)

glow = glow.filter(ImageFilter.GaussianBlur(28 * S))
final = ImageChops.add(img, ImageChops.multiply(glow, Image.new("RGB", img.size, (110, 110, 110))))
final = final.resize((W, H), Image.LANCZOS)
here = Path(__file__).parent
tmp = here / "devto-cover.tmp.jpg"
final.save(tmp, quality=92)
h = hashlib.sha256(tmp.read_bytes()).hexdigest()[:8]
dst = here / f"devto-cover.{h}.jpg"
tmp.rename(dst)
print(dst.name, f"{W}x{H}", f"{dst.stat().st_size // 1024} KB")
