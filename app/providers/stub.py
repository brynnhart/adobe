from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple
import random

class StubProvider:
    def generate(self, prompt: str, size: Tuple[int, int]) -> Image.Image:
        w, h = size
        img = Image.new('RGB', (w, h), (24, 26, 30))
        d = ImageDraw.Draw(img)
        # gradient-ish
        for y in range(h):
            val = 24 + int(120 * (y / max(1, h-1)))
            d.line([(0, y), (w, y)], fill=(val, val-12, val-20))
        # accents
        for _ in range(5):
            cx = random.randint(int(0.1*w), int(0.9*w))
            cy = random.randint(int(0.1*h), int(0.9*h))
            r = random.randint(int(min(w,h)*0.05), int(min(w,h)*0.15))
            col = (random.randint(80,160), random.randint(60,120), random.randint(60,150))
            d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=3)
        return img
