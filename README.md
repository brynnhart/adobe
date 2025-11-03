# Creative Automation (CLI) — OpenAI Provider

A command-line proof of concept that ingests a campaign brief (YAML/JSON), reuses local assets where available, generates missing hero images with the OpenAI Images API, and exports social-ready creatives in multiple aspect ratios with brand overlays.  
Includes optional text tasks (e.g., translation) and **brand/legal compliance checking** with intelligent term replacement.

---

## Overview

This project demonstrates an **automated creative generation pipeline** for marketing content.  
It transforms a structured campaign brief into ready-to-publish social ads while enforcing compliance and brand consistency.

The focus is **pipeline logic, modularity, and automation readiness**, not UI polish — the kind of backend system that could later power a web dashboard, internal automation bot, or Adobe Firefly workflow.

---

## Core Features

- **Brief-driven pipeline**
  - Campaigns define products, target audiences, regions, and core messages.
- **Smart asset sourcing**
  - Reuse local hero assets when available.
  - Otherwise, auto-generate via **OpenAI Images** (`gpt-image-1`).
- **Aspect ratio variants**
  - Generates 1:1, 9:16, and 16:9 creatives (extendable in config).
- **Dynamic layout**
  - Brand color band with logo placement and adaptive text sizing.
  - Automatically fits or wraps text intelligently.
- **Optional text intelligence**
  - Translate or localize headlines using OpenAI Chat (off by default).
- **Brand compliance**
  - Checks for logo presence, brand color use, and visual consistency.
- **Legal/linguistic compliance**
  - Flags or replaces prohibited marketing terms.
  - Rules stored externally in `config/compliance_rules.json` for easy editing.
  - Safe substitutions supported (e.g., `"guaranteed" → "backed by our policy"`).
- **Reporting**
  - Generates structured JSON + CSV run reports.
  - Verbose CLI logs highlight compliance actions and API calls.
- **Modular provider design**
  - Swap OpenAI for **Adobe Firefly** or another provider with zero pipeline changes.

---

## Project Structure

```
app/
 ├── main.py                 # CLI entrypoint
 ├── pipeline.py             # Main orchestration logic
 ├── providers/
 │    └── openai_images.py   # Image generation provider
 ├── layout/
 │    └── templater.py       # Text and layout logic
 ├── compliance/
 │    └── rules.py           # Term checking + replacements
 ├── io/
 │    └── files.py           # I/O and save utilities
 └── util/logger.py          # Console formatting
briefs/
 └── sample.yaml             # Example input brief
config/
 └── compliance_rules.json   # Centralized compliance terms
assets/
 ├── fonts/Inter_24pt-Regular.ttf
 └── logos/
outputs/
 └── <campaign_id>/<product>/<ratio>/post_<n>.png
```

---

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # then edit with your keys
```

### Environment Variables

| Variable | Description |
|-----------|-------------|
| `OPENAI_API_KEY` | Required to call OpenAI (not stored in repo). |
| `OPENAI_ORG_ID` | Optional, used for organization-based auth. |
| `OPENAI_BASE_URL` | Optional (for Azure/OpenAI-compatible gateways). |
| `OPENAI_TEXT_MODEL` | Defaults to `gpt-4o-mini`. |
| `OPENAI_IMAGE_MODEL` | Defaults to `gpt-image-1`. |
| `ENABLE_TRANSLATION` | `1` enables localized message translation. |
| `COMPLIANCE_RULES_PATH` | Path to compliance JSON file. |
| `COMPLIANCE_SANITIZE` | `1` replaces unsafe terms with approved alternatives. |
| `FORCE_GENERATE` | `1` forces regeneration even if assets exist. |
| `HEADLINE_SCALE` | `1` Overall scale of text. |
| `HEADLINE_MAX_LINES` | `1` Maximum number of lines text is allowed to wrap. |

> You can export these directly in your shell instead of using `.env`.

---

## Running the Pipeline

```bash
python -m app.main --brief briefs/sample.yaml --out outputs/ --variants 2
```

### Example Output

```
outputs/
 └── fall-espresso-2025/
     ├── espresso/
     │   ├── 1x1/post_1.png
     │   ├── 9x16/post_1.png
     │   └── 16x9/post_1.png
     ├── run_report.json
     └── run_report.csv
```

### Example Console Output

```
[INFO] Processing campaign fall-espresso-2025
[INFO] Loaded 6 prohibited terms for compliance checking.
[INFO] [16:9] Generating via OpenAI Images…
[INFO] ✅ Compliance: replaced prohibited terms in headline for Pour-over Kit
[INFO]    → "guaranteed" → "backed by our policy"
[INFO] Run complete: 6 creatives saved (compliance: 2 sanitized, 0 warnings)
```

---

## Brief Format Example

```yaml
campaign_id: fall-espresso-2025
brand:
  name: Moss & Ember Coffee
  colors: ["#734F3B"]
  logo_path: assets/logos/moss_ember.png
target:
  region: US
  audience: Young professionals
message:
  en: "Guaranteed energy for focused mornings."
products:
  - id: espresso
    name: "Espresso Pods"
    hero_asset: assets/products/espresso.png
  - id: pour_over
    name: "Pour-over Kit"
    hero_asset: ""
variants:
  aspect_ratios: ["1:1", "9:16", "16:9"]
  count_per_product: 2
```

---

## Compliance System

- **Configuration:** `config/compliance_rules.json`
- **Mode:** flag-only by default, or auto-replace with `COMPLIANCE_SANITIZE=1`
- **Example:**
  ```json
  {
    "prohibited_terms": {
      "guaranteed": "backed by our policy",
      "free": "complimentary",
      "100% safe": "safety-tested"
    }
  }
  ```
- **Console feedback:**
  ```
  ✅ Compliance: replaced prohibited terms in headline for Espresso Pods
     → "guaranteed" → "backed by our policy"
  ```

---

##  Design Decisions

- **CLI-first architecture** — lightweight, easily automated by a scheduler or agent.
- **Provider abstraction** — Firefly or DALLE can be swapped without pipeline edits.
- **Externalized compliance rules** — editable without code.
- **Composable, testable modules** — clear separation of I/O, provider logic, and layout.
- **Future-ready for agentic orchestration** — the pipeline could be wrapped by a simple “creative agent” monitoring briefs and generating assets automatically.

---

##  Next Steps (Future Enhancements)

- **Firefly Adapter:** Replace `OpenAIImageProvider` with Firefly API for native Adobe integration.
- **Agentic Automation Layer:** Detect new briefs, run the pipeline, and summarize output via LLM (Task 2 deliverable).
- **Visual Dashboard:** Extend CLI logs into a small web UI for monitoring creative production.
- **Template Library:** Expand layouts beyond bottom-band format.
- **Figma/Cloud Sync:** Export results to shared asset repositories or creative management tools.

---

## License
MIT — for interview demonstration purposes only.

---

## Maintainer
**Brynn Hart**  
brynnhart@gmail.com  
Creative Technologist / AI Automation Engineer  
