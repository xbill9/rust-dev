#!/usr/bin/env python3
"""Builder Center cover (1200x675, AWS's recommended size): the dev.to cover
scaled to 1200 wide and centred on the same background, content-addressed."""
import hashlib, sys
from pathlib import Path
from PIL import Image

here = Path(__file__).parent
src = here / (sys.argv[1] if len(sys.argv) > 1 else "devto-cover.69a65719.jpg")
im = Image.open(src).convert("RGB")
w = 1200
h = round(im.height * w / im.width)
canvas = Image.new("RGB", (1200, 675), im.getpixel((2, 2)))
canvas.paste(im.resize((w, h), Image.LANCZOS), (0, (675 - h) // 2))
tmp = here / "builder-cover.tmp.jpg"
canvas.save(tmp, quality=92)
dst = here / f"builder-cover.{hashlib.sha256(tmp.read_bytes()).hexdigest()[:8]}.jpg"
tmp.rename(dst)
print(dst.name, canvas.size, f"{dst.stat().st_size // 1024} KB")
