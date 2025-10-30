from typing import Tuple
from PIL import Image
import io, base64, os, time

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

class OpenAIImageProvider:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", None)
        self.org_id = os.getenv("OPENAI_ORG_ID", "org-qgeI8WCGdMlyC4rLTFNOZNFm")

        if OpenAI and self.api_key:
            if self.base_url:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    organization=self.org_id
                )
            else:
                self.client = OpenAI(
                    api_key=self.api_key,
                    organization=self.org_id
                )
        else:
            self.client = None

    def generate(self, prompt: str, size: Tuple[int, int]) -> Image.Image:
        if not self.client:
            return Image.new("RGB", size, (54, 54, 60))

        target = max(256, min(1024, max(size)))
        t0 = time.time()
        resp = self.client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=f"{target}x{target}",
            n=1
        )
        dt = int((time.time() - t0) * 1000)
        print(f"[INFO] OpenAI image generated in {dt} ms, requested={target}x{target}")
        b64 = resp.data[0].b64_json
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        return img.resize(size, Image.LANCZOS)
