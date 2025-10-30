import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")

class OpenAIText:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", None)
        if OpenAI and self.api_key:
            if self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def translate(self, text: str, target_lang_code: str) -> Optional[str]:
        if not self.client:
            return None
        prompt = f"Translate the following marketing headline into {target_lang_code}. Return only the translation. Keep it concise and natural for ads.\n\n{text}"
        resp = self.client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": "You are a concise, accurate translator for marketing copy."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or '').strip()
