from typing import List, Optional
from pathlib import Path
from PIL import Image

def has_logo(logo_path: Optional[str], min_size: int = 64) -> bool:
    if not logo_path or not Path(logo_path).exists():
        return False
    try:
        with Image.open(logo_path) as im:
            w, h = im.size
            return w >= min_size and h >= min_size
    except Exception:
        return False

def uses_brand_color(brand_colors: List[str]) -> bool:
    return bool(brand_colors)

def has_prohibited_terms(text: str, terms: List[str]) -> List[str]:
    found = []
    low = (text or '').lower()
    for t in terms or []:
        if t.lower() in low:
            found.append(t)
    return found
