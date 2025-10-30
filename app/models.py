from pydantic import BaseModel, Field, RootModel
from typing import List, Optional, Dict

class Brand(BaseModel):
    name: str
    colors: List[str] = Field(default_factory=list)
    logo_path: Optional[str] = None

class Product(BaseModel):
    id: str
    name: str
    hero_asset: Optional[str] = None

class Target(BaseModel):
    region: str
    audience: str

class Variants(BaseModel):
    aspect_ratios: List[str] = Field(default_factory=lambda: ["1:1", "9:16", "16:9"])
    count_per_product: int = 2

class Legal(BaseModel):
    prohibited_terms: List[str] = Field(default_factory=list)

# ✅ Pydantic v2 root model
class Message(RootModel[Dict[str, str]]):
    def get_for_lang(self, lang: str) -> Optional[str]:
        return self.root.get(lang)

    def get_default(self) -> str:
        return self.root.get("en") or next(iter(self.root.values()))

class Brief(BaseModel):
    campaign_id: str
    brand: Brand
    products: List[Product]
    target: Target
    message: Message
    variants: Variants = Variants()
    legal: Optional[Legal] = None
