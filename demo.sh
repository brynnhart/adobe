#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate || .venv\Scripts\activate

pip install -r requirements.txt

# Fill OPENAI_API_KEY in your env or .env first
python -m app.main --brief briefs/sample.yaml --out outputs/ --variants 2

echo "Done. Check the outputs/ folder."
