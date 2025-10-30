# app/layout/templater.py
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from typing import Optional, List, Tuple
import os

# ---------- FONT LOADING (repo-root assets/fonts) ----------
def get_font(size: int = 48) -> ImageFont.FreeTypeFont:
    """
    Load Inter Regular from <repo>/assets/fonts/Inter_24pt-Regular.ttf.
    Falls back to a couple of system fonts, then Pillow default.
    """
    here = Path(__file__).resolve()
    root = here.parents[2]  # .../adobe (layout -> app -> <repo root>)
    candidates = [
        root / "assets" / "fonts" / "Inter_24pt-Regular.ttf",  # your actual path
        root / "assets" / "font"  / "Inter_24pt-Regular.ttf",  # alt singular
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                # print(f"[INFO] Using font: {p}")
                return ImageFont.truetype(str(p), size=int(size))
        except Exception as e:
            print(f"[WARN] Tried {p} but failed: {e}")
    print("[WARN] No TrueType font found. Falling back to Pillow default bitmap font (tiny).")
    return ImageFont.load_default()

# ---------- CROPPING HELPERS ----------
def _energy_map(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return edges

def _best_crop_rect(img: Image.Image, target_ratio: float) -> tuple[int, int, int, int]:
    W, H = img.size
    edges = _energy_map(img)
    epx = edges.load()
    step_x = max(8, W // 80)
    step_y = max(8, H // 80)
    cands = []
    crop_h = int(W / target_ratio)
    if crop_h <= H:
        for y0 in range(0, H - crop_h + 1, step_y):
            cands.append((0, y0, W, y0 + crop_h))
    crop_w = int(H * target_ratio)
    if crop_w <= W:
        for x0 in range(0, W - crop_w + 1, step_x):
            cands.append((x0, 0, x0 + crop_w, H))
    best, best_score = (0, 0, W, H), -1e9
    for (x0, y0, x1, y1) in cands:
        score = 0.0
        sx = max(1, (x1 - x0) // 40)
        sy = max(1, (y1 - y0) // 40)
        for yy in range(y0, y1, sy):
            for xx in range(x0, x1, sx):
                score += epx[xx, yy]
        lower_bias = (y1 / H) * 0.05
        score *= (1.0 + lower_bias)
        if score > best_score:
            best_score, best = score, (x0, y0, x1, y1)
    return best

def to_ratio(img: Image.Image, ratio: str, smart_top_trim: bool = True) -> Image.Image:
    w, h = img.size
    a, b = map(int, ratio.split(":"))
    target = a / b
    cur = w / h
    if abs(cur - target) < 1e-6:
        return img.copy()
    x0, y0, x1, y1 = _best_crop_rect(img, target)
    return img.crop((x0, y0, x1, y1))

# ---------- TEXT FIT HELPERS ----------
def _measure_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, stroke_w: int = 0) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def _hard_break_token(draw: ImageDraw.ImageDraw, token: str, font: ImageFont.FreeTypeFont,
                      max_width: int, stroke_w: int) -> List[str]:
    """
    Breaks a single overlong token into hyphenated chunks that each fit max_width.
    Example: "supercalifragilisticexpialidocious" -> ["supercali-", "fragilist-", "icexpiali-", "docious"]
    """
    chunks: List[str] = []
    cur = ""
    for ch in token:
        test = (cur + ch)
        wpx, _ = _measure_line(draw, test + "-", font, stroke_w)  # measure with a hyphen
        if wpx <= max_width:
            cur = test
        else:
            if cur:
                chunks.append(cur + "-")
                cur = ch
            else:
                # single char doesn't even fit; force append to avoid infinite loop
                chunks.append(ch)
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks

def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                   max_width: int, max_lines: int, stroke_w: int) -> List[str]:
    """
    Word-wrap text so each line fits max_width using current font and stroke width.
    Handles overlong tokens by hyphenating.
    Returns up to max_lines lines (last line may be truncated with ellipsis).
    """
    if not text:
        return []
    words = text.strip().split()
    if not words:
        return []

    lines: List[str] = []
    cur = ""

    for token in words:
        # If token alone is too wide, hyphenate it
        token_width, _ = _measure_line(draw, token, font, stroke_w)
        if token_width > max_width:
            hyph = _hard_break_token(draw, token, font, max_width, stroke_w)
            for sub in hyph:
                test = (cur + " " + sub).strip()
                wpx, _ = _measure_line(draw, test, font, stroke_w)
                if wpx <= max_width or not cur:
                    cur = test
                else:
                    lines.append(cur)
                    cur = sub
                if len(lines) == max_lines:
                    break
            if len(lines) == max_lines:
                break
            continue

        # Normal token flow
        test = (cur + " " + token).strip()
        wpx, _ = _measure_line(draw, test, font, stroke_w)
        if wpx <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = token
        if len(lines) == max_lines:
            break

    if len(lines) < max_lines and cur:
        lines.append(cur)

    # If still too wide on the last line, truncate with ellipsis
    if lines:
        last = lines[-1]
        while _measure_line(draw, last + "…", font, stroke_w)[0] > max_width and len(last) > 1:
            last = last[:-1]
        if last != lines[-1]:
            lines[-1] = last + "…"

    return lines[:max_lines]

def _fit_text_block(draw: ImageDraw.ImageDraw, text: str, font_loader,
                    max_w: int, max_h: int, ar: float) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    """
    Choose a font size (via binary search) and wrapping that fits in (max_w, max_h).
    Returns (font, wrapped_lines, line_height_px).
    If it cannot fit using the preferred line count, it will escalate to more lines (up to 3).
    """
    # Preferred max lines by ratio
    preferred = 1 if ar >= 1.4 else (3 if ar < 0.9 else 2)
    for allowed_lines in range(preferred, 4):  # try preferred, then escalate to 3
        lo, hi = 18, max(26, int(max_h * (0.95 if ar <= 0.8 else 0.80)))  # upper bound guess
        best = None
        for _ in range(12):  # binary search
            mid = max(lo, min(hi, (lo + hi) // 2))
            font = font_loader(mid)
            stroke_w = max(2, int(font.size * 0.07))
            lines = _wrap_to_width(draw, text, font, max_w, allowed_lines, stroke_w)

            # measure block with stroke
            _, line_h = _measure_line(draw, "Ag", font, stroke_w)
            step = int(line_h * 1.1)  # 10% line spacing
            total_h = len(lines) * step
            widest = max((_measure_line(draw, ln, font, stroke_w)[0] for ln in lines), default=0)

            fits = (widest <= max_w) and (total_h <= max_h) and len(lines) > 0
            if fits:
                best = (font, lines, step)
                lo = mid + 1
            else:
                hi = mid - 1

        if best is not None:
            return best

    # Absolute fallback (tiny but guaranteed)
    font = font_loader(20)
    stroke_w = max(2, int(font.size * 0.07))
    lines = _wrap_to_width(draw, text, font, max_w, 3, stroke_w)
    _, line_h = _measure_line(draw, "Ag", font, stroke_w)
    step = int(line_h * 1.1)
    return font, lines, step

# ---------- MAIN LAYOUT ----------
def apply_template(base: Image.Image, headline: str, brand_colors: list[str], logo_path: Optional[str]) -> Image.Image:
    """
    Ratio-aware band, logo reservation, and auto-wrapped/shrink-to-fit headline.
    """
    img = base.copy().convert("RGBA")
    w, h = img.size
    ar = w / h
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Band height by aspect ratio
    if ar >= 1.4:      # 16:9-ish
        band_h = int(h * 0.18)
    elif ar <= 0.8:    # 9:16-ish
        band_h = int(h * 0.22)
    else:              # 1:1-ish
        band_h = int(h * 0.20)
    band_y = h - band_h

    # Band color (brand-tinted with alpha)
    band_color = (0, 0, 0, 190)
    if brand_colors:
        try:
            c = brand_colors[0].lstrip("#")
            band_color = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 200)
        except Exception:
            pass
    band = Image.new("RGBA", (w, band_h), band_color)
    overlay.alpha_composite(band, (0, band_y))

    # Logo first: reserve space on the right (values from your current version)
    right_margin = int(w * 0.04)
    left_margin  = int(w * 0.06)
    logo_w_reserved = 0
    logo_img = None
    if logo_path and Path(logo_path).exists():
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            # Height target (tune as you like)
            if ar >= 1.4:        # wide 16:9
                target_h = int(band_h * 1.10)
            elif ar <= 0.8:      # tall 9:16
                target_h = int(band_h * 0.80)
            else:                # square
                target_h = int(band_h * 0.80)
            target_h = min(target_h, band_h - 2)
            scale = target_h / max(1, logo_img.height)
            logo_img = logo_img.resize((int(logo_img.width * scale), target_h), Image.LANCZOS)
            logo_w_reserved = logo_img.width + right_margin
        except Exception:
            logo_img = None
            logo_w_reserved = 0

    # Text block area (left to logo)
    text_max_w = max(80, w - left_margin - logo_w_reserved - right_margin)
    text_max_h = int(band_h * (0.82 if ar >= 1.4 else 0.88))  # a bit more room for portrait
    text_y0    = band_y + (band_h - text_max_h) // 2

    # Fit text (size + wrapping)
    font_loader = lambda sz: get_font(sz)
    font, lines, line_step = _fit_text_block(draw, headline, font_loader, text_max_w, text_max_h, ar)
    stroke_w = max(2, int(font.size * 0.07))
    pen = (255, 255, 255, 255)
    stroke = (0, 0, 0, 220)

    # Draw lines (left-aligned) with stroke, vertically centered in text box
    total_h = len(lines) * line_step
    ty = text_y0 + (text_max_h - total_h) // 2
    for i, ln in enumerate(lines):
        draw.text((left_margin, ty + i * line_step), ln, font=font,
                  fill=pen, stroke_width=stroke_w, stroke_fill=stroke)

    # Place logo last
    if logo_img is not None:
        lx = w - right_margin - logo_img.width
        ly = band_y + (band_h - logo_img.height) // 2
        overlay.alpha_composite(logo_img, (lx, ly))

    out = Image.alpha_composite(img, overlay)
    return out.convert("RGB")
