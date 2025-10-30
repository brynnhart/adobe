from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple
from PIL import Image
import os
import time

from .models import Brief
from .io.files import ensure_dir, save_json, save_csv
from .layout.templater import to_ratio, apply_template
from .checks.compliance import has_logo, uses_brand_color
from .util.logger import info, warn
from .compliance.rules import ComplianceRules, check_message


def translate_if_needed(brief: Brief, lang: str) -> str:
    msg = brief.message.get_for_lang(lang)
    return msg if msg else brief.message.get_default()


def _asset_valid(path: str | None, min_px: int = 256) -> bool:
    """Consider an asset reusable only if it exists, decodes, and is reasonably sized."""
    if not path:
        return False
    p = Path(path)
    if not p.exists():
        return False
    try:
        with Image.open(p) as im:
            w, h = im.size
            return (w >= min_px and h >= min_px)
    except Exception:
        return False


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _run_check_message(text: str, rules: ComplianceRules) -> Tuple[str, list[str], bool, Dict[str, str]]:
    """
    Wrapper that tolerates either 3-tuple or 4-tuple returns from check_message():
      - (cleaned, remaining, modified)
      - (cleaned, remaining, modified, replacements)
    Returns a normalized 4-tuple: (cleaned, remaining, modified, replacements).
    """
    res = check_message(text, rules)
    # If rules.check_message returns a tuple of 3 or 4 elements, normalize
    if isinstance(res, tuple):
        if len(res) == 4:
            cleaned, remaining, modified, replacements = res
        elif len(res) == 3:
            cleaned, remaining, modified = res
            replacements = {}
        else:
            # Unexpected shape; fall back safely
            cleaned, remaining, modified, replacements = text, [], False, {}
    else:
        # Unexpected return type; fall back to original text
        cleaned, remaining, modified, replacements = text, [], False, {}
    # Ensure types
    remaining = list(remaining) if remaining else []
    replacements = dict(replacements) if replacements else {}
    return cleaned, remaining, bool(modified), replacements


def process_campaign(brief: Brief, out_dir: str, variants_override: int | None = None):
    """
    Main pipeline orchestration:
      1) Generate or reuse hero assets (with validation and FORCE_GENERATE override)
      2) Crop to required ratios
      3) Apply brand overlays
      4) Compliance checks (with demo-friendly logs)
      5) Save outputs + reports
    """
    info(f"Processing campaign {brief.campaign_id}")
    ensure_dir(out_dir)

    # Provider (lazy import)
    from .providers.openai_images import OpenAIImageProvider
    provider = OpenAIImageProvider()

    ratios = brief.variants.aspect_ratios
    num_variants = variants_override or brief.variants.count_per_product
    report_rows: list[dict[str, Any]] = []

    # Centralized compliance rules
    rules = ComplianceRules.load()
    info(f"Loaded {len(rules.prohibited_terms)} prohibited terms for compliance checking.")

    force_generate = _bool_env("FORCE_GENERATE", default=False)
    info(f"FORCE_GENERATE={'on' if force_generate else 'off'}")

    # Track compliance summary for a nicer demo close-out
    total_creatives = 0
    total_sanitized = 0
    total_with_violations = 0

    for product in brief.products:
        info(f"  Product: {product.name}")
        product_dir = Path(out_dir) / brief.campaign_id / product.id
        ensure_dir(product_dir)

        product_sanitized = 0
        product_violations = 0

        for ratio in ratios:
            ratio_dir = product_dir / ratio.replace(":", "x")
            ensure_dir(ratio_dir)

            for idx in range(num_variants):
                total_creatives += 1

                # --- 1) Reuse vs generate (validated) ---
                use_reuse = (not force_generate) and _asset_valid(product.hero_asset)
                if use_reuse:
                    base = Image.open(product.hero_asset).convert("RGB")
                    source = "reused"
                    info(f"    [{ratio}] Reusing asset: {product.hero_asset}")
                else:
                    # ratio-aware composition hints
                    if ratio == "9:16":
                        framing = "vertical portrait framing, subject fully in frame, negative space at bottom third"
                    elif ratio == "16:9":
                        framing = "wide landscape framing, subject fully in frame, negative space at bottom third"
                    else:
                        framing = "square centered framing, subject fully in frame, negative space at bottom third"

                    prompt = (
                        f"Studio product hero photograph of '{product.name}' for {brief.target.region} "
                        f"{brief.target.audience} social ad. Moody, premium lighting, clean backdrop, "
                        f"{framing}. NO text, NO labels, NO logos, NO typography, NO captions, NO watermarks."
                    )

                    try:
                        t0 = time.time()
                        info(f"    [{ratio}] Generating via OpenAI Images…")
                        base = provider.generate(prompt, (1536, 1536))
                        dt = (time.time() - t0) * 1000
                        info(f"    [{ratio}] OpenAI generation returned in {dt:.0f} ms, size={getattr(base, 'size', None)}")
                        # Optional: persist the raw generation before any crop/overlay (disabled by default)
                        # raw_path = ratio_dir / f"_raw_gen_{idx + 1}.png"
                        # base.save(raw_path, "PNG")
                        source = "generated"
                    except Exception as e:
                        warn(f"    OpenAI generation failed ({e!r}); using neutral placeholder.")
                        base = Image.new("RGB", (1536, 1536), (54, 54, 60))
                        # Save a proper PNG so it's viewable
                        (ratio_dir / f"_raw_fallback_{idx + 1}.png").write_bytes(b"")  # create marker
                        base.save(ratio_dir / f"_raw_fallback_{idx + 1}.png", "PNG")
                        source = "fallback"

                # --- 2) Aspect ratio crop ---
                if not isinstance(base, Image.Image) or base.size[0] < 128 or base.size[1] < 128:
                    raise RuntimeError("Provider did not return a valid image. Check API key/org/model settings.")
                base = to_ratio(base, ratio)

                # --- 3) Compliance check on message (demo-friendly logging) ---
                lang = brief.target.region.lower()
                headline_raw = translate_if_needed(brief, lang)

                cleaned, remaining, modified, replacements = _run_check_message(headline_raw, rules)
                headline = cleaned

                # Verbose messages for demo
                if remaining and not modified:
                    product_violations += 1
                    total_with_violations += 1
                    warn(f"    ⚠️ Compliance: {remaining} found in headline(no replacements applied)")
                elif modified and replacements:
                    product_sanitized += 1
                    total_sanitized += 1
                    info(f"    ✅ Compliance: replaced prohibited terms in headline")
                    for bad, good in replacements.items():
                        info(f"       → \"{bad}\" → \"{good}\"")
                elif modified:
                    product_sanitized += 1
                    total_sanitized += 1
                    info(f"    ✅ Compliance: sanitized headline")

                # --- 4) Apply brand overlay ---
                result = apply_template(
                    base,
                    headline=headline,
                    brand_colors=brief.brand.colors,
                    logo_path=brief.brand.logo_path,
                )

                # --- 5) Save output ---
                out_path = ratio_dir / f"post_{idx + 1}.png"
                result.save(out_path, "PNG")

                # --- 6) QC checks + report row ---
                logo_ok = has_logo(brief.brand.logo_path)
                brand_color_ok = uses_brand_color(brief.brand.colors)

                report_rows.append({
                    "campaign_id": brief.campaign_id,
                    "product_id": product.id,
                    "product_name": product.name,
                    "ratio": ratio,
                    "variant": idx,
                    "source": source,
                    "logo_present": logo_ok,
                    "brand_color_applied": brand_color_ok,
                    "prohibited_terms_found": ";".join(remaining),
                    "compliance_modified_copy": "yes" if modified else "no",
                })

        # Per-product compliance summary (nice for demos)
        if product_sanitized or product_violations:
            info(f"  └─ Compliance summary for {product.name}: "
                 f"{product_sanitized} sanitized, {product_violations} with warnings")

    # --- 7) Save run report ---
    run_root = Path(out_dir) / brief.campaign_id
    ensure_dir(run_root)
    save_json(run_root / "run_report.json", report_rows)
    save_csv(run_root / "run_report.csv", report_rows)

    # Final one-line compliance summary (demo polish)
    info(f"Run complete: {len(report_rows)} creatives saved to {run_root} "
         f"(compliance: {total_sanitized} sanitized, {total_with_violations} with warnings)")
