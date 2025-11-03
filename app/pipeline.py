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

# --- Try both possible locations for your translator ---
try:
    from .providers.openai_text import OpenAIText  # preferred (app/providers/openai_text.py)
except Exception:
    try:
        from .openai_text import OpenAIText        # fallback (app/openai_text.py)
    except Exception:
        OpenAIText = None  # handled later


# ----------------- helpers -----------------
def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


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


_REGION_TO_LANG = {
    "us": "en", "uk": "en", "gb": "en", "ca": "en",
    "de": "de", "at": "de", "ch": "de",
    "fr": "fr", "be": "fr",
    "es": "es", "mx": "es", "ar": "es", "co": "es",
    "it": "it", "pt": "pt", "br": "pt",
    "nl": "nl", "se": "sv", "no": "no", "dk": "da",
    "fi": "fi", "pl": "pl", "cz": "cs",
    "jp": "ja", "kr": "ko", "cn": "zh", "tw": "zh-TW",
}


def _derive_target_lang(brief: Brief) -> str:
    """Env override > brief.target.language > brief.target.region -> language > 'en'."""
    env_lang = os.getenv("TARGET_LANG")
    if env_lang:
        return env_lang.strip()

    target_lang = getattr(brief.target, "language", None)
    if target_lang:
        return str(target_lang).strip()

    region = str(getattr(brief.target, "region", "")).lower()
    return _REGION_TO_LANG.get(region, "en")


def _get_existing_local(brief: Brief, lang: str) -> str | None:
    """Return localized message from brief if present, else None."""
    try:
        msg = brief.message.get_for_lang(lang)
        return msg if msg else None
    except Exception:
        return None


def _get_default_msg(brief: Brief) -> str:
    try:
        return brief.message.get_default() or ""
    except Exception:
        return ""


def _check_message4(text: str, rules: ComplianceRules) -> Tuple[str, list[str], bool, Dict[str, str]]:
    """
    Normalize check_message() to always return 4 values:
      (cleaned, remaining, modified, replacements)

    Works with implementations that return:
      - 4-tuple: (cleaned, remaining, modified, replacements)
      - 3-tuple: (cleaned, remaining, modified)
    """
    res = check_message(text, rules)
    if isinstance(res, tuple):
        if len(res) == 4:
            cleaned, remaining, modified, replacements = res
        elif len(res) == 3:
            cleaned, remaining, modified = res
            replacements = {}
        else:
            cleaned, remaining, modified, replacements = text, [], False, {}
    else:
        cleaned, remaining, modified, replacements = text, [], False, {}
    return cleaned, list(remaining) if remaining else [], bool(modified), dict(replacements)


def _compute_final_headline_once(
    brief: Brief,
    rules: ComplianceRules,
    enable_translation: bool,
    tgt_lang: str
) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Compute the campaign headline exactly once:
      1) Use existing localized headline if available for tgt_lang.
      2) Else take default (assume English), run pre-translation compliance (single-language rules).
      3) Translate the sanitized text ONCE if enabled and tgt_lang != en.

    Returns: (final_headline, was_translated, meta)
      meta includes counts for sanitized/warnings and any replacement map for logging/report.
    """
    # 1) Use existing localized copy if present
    existing_local = _get_existing_local(brief, tgt_lang)
    if existing_local:
        info(f"[i18n] Using existing localized headline for '{tgt_lang}'. (No translation needed)")
        return existing_local, False, {
            "source": "localized",
            "sanitized": 0,
            "violations": 0,
            "replacements": {}
        }

    # 2) Start from default (assume English)
    source_text = _get_default_msg(brief)
    if not source_text:
        warn("[i18n] No default message found in brief; headline will be empty.")
        return "", False, {
            "source": "empty",
            "sanitized": 0,
            "violations": 0,
            "replacements": {}
        }

    # Pre-translation compliance (English-only rules)
    cleaned_src, remaining_src, modified_src, repl_src = _check_message4(source_text, rules)
    if remaining_src and not modified_src:
        warn(f"⚠️ Compliance (pre-translation): {remaining_src} (no replacements applied)")
    elif modified_src and repl_src:
        info("✅ Compliance (pre-translation): replaced prohibited terms")
        for bad, good in repl_src.items():
            info(f'   → "{bad}" → "{good}"')
    elif modified_src:
        info("✅ Compliance (pre-translation): sanitized headline")

    headline_pre = cleaned_src
    sanitized_cnt = 1 if modified_src else 0
    violations_cnt = 1 if (remaining_src and not modified_src) else 0

    # 3) Single translation call (if enabled and not English target)
    if enable_translation and not tgt_lang.lower().startswith("en"):
        if OpenAIText is None:
            warn("[i18n] Translation requested but OpenAIText is unavailable. Using sanitized English.")
            return headline_pre, False, {
                "source": "sanitized_en",
                "sanitized": sanitized_cnt,
                "violations": violations_cnt,
                "replacements": repl_src
            }
        try:
            translator = OpenAIText()
            translated = translator.translate(headline_pre, tgt_lang)
            if translated:
                info(f"[i18n] Translated sanitized headline to '{tgt_lang}' (cached for all creatives).")
                return translated, True, {
                    "source": "translated",
                    "sanitized": sanitized_cnt,
                    "violations": violations_cnt,
                    "replacements": repl_src
                }
            else:
                warn(f"[i18n] Translation returned empty for '{tgt_lang}'. Using sanitized English.")
                return headline_pre, False, {
                    "source": "sanitized_en",
                    "sanitized": sanitized_cnt,
                    "violations": violations_cnt,
                    "replacements": repl_src
                }
        except Exception as e:
            warn(f"[i18n] Translation error for '{tgt_lang}': {e!r}. Using sanitized English.")
            return headline_pre, False, {
                "source": "sanitized_en",
                "sanitized": sanitized_cnt,
                "violations": violations_cnt,
                "replacements": repl_src
            }
    else:
        info(f"[i18n] Translation skipped (lang='{tgt_lang}'). Using sanitized English.")
        return headline_pre, False, {
            "source": "sanitized_en",
            "sanitized": sanitized_cnt,
            "violations": violations_cnt,
            "replacements": repl_src
        }


# ----------------- main pipeline -----------------
def process_campaign(brief: Brief, out_dir: str, variants_override: int | None = None):
    """
    Main pipeline orchestration (headline computed once per campaign):
      1) Compute final headline ONCE (localized OR sanitized English OR translated sanitized)
      2) Generate or reuse hero assets
      3) Crop to required ratios
      4) Apply brand overlays with the cached headline
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
    enable_translation = _bool_env("ENABLE_TRANSLATION", default=False)
    info(f"FORCE_GENERATE={'on' if force_generate else 'off'}")
    info(f"ENABLE_TRANSLATION={'on' if enable_translation else 'off'}")

    tgt_lang = _derive_target_lang(brief)

    # ---- Compute the headline ONCE and cache it ----
    final_headline, headline_was_translated, headline_meta = _compute_final_headline_once(
        brief=brief,
        rules=rules,
        enable_translation=enable_translation,
        tgt_lang=tgt_lang
    )

    # Nice summary log for the run
    info(f"[i18n] Headline source: {headline_meta.get('source')}; "
         f"translated={'yes' if headline_was_translated else 'no'}; "
         f"pre-sanitized={'yes' if headline_meta.get('sanitized') else 'no'}; "
         f"pre-violations={'yes' if headline_meta.get('violations') else 'no'}")

    # Track totals just for a clean final log
    total_creatives = 0

    for product in brief.products:
        info(f"  Product: {product.name}")
        product_dir = Path(out_dir) / brief.campaign_id / product.id
        ensure_dir(product_dir)

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
                        source = "generated"
                    except Exception as e:
                        warn(f"    OpenAI generation failed ({e!r}); using neutral placeholder.")
                        base = Image.new("RGB", (1536, 1536), (54, 54, 60))
                        (ratio_dir / f"_raw_fallback_{idx + 1}.png").write_bytes(b"")  # marker
                        base.save(ratio_dir / f"_raw_fallback_{idx + 1}.png", "PNG")
                        source = "fallback"

                # --- 2) Aspect ratio crop ---
                if not isinstance(base, Image.Image) or base.size[0] < 128 or base.size[1] < 128:
                    raise RuntimeError("Provider did not return a valid image. Check API key/org/model settings.")
                base = to_ratio(base, ratio)

                # --- 3) Apply brand overlay with cached headline ---
                result = apply_template(
                    base,
                    headline=final_headline,
                    brand_colors=brief.brand.colors,
                    logo_path=brief.brand.logo_path,
                )

                # --- 4) Save output ---
                out_path = ratio_dir / f"post_{idx + 1}.png"
                result.save(out_path, "PNG")

                # --- 5) QC checks + report row ---
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
                    "target_lang": tgt_lang,
                    "translated": "yes" if headline_was_translated else "no",
                })

    # --- Save run report ---
    run_root = Path(out_dir) / brief.campaign_id
    ensure_dir(run_root)
    save_json(run_root / "run_report.json", report_rows)
    save_csv(run_root / "run_report.csv", report_rows)

    info(f"Run complete: {len(report_rows)} creatives saved to {run_root}")
