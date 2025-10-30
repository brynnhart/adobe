import os, json, yaml, csv
from pathlib import Path
from typing import Any, Dict
from ..models import Brief

def load_brief(path: str) -> Brief:
    p = Path(path)
    with open(p, 'r', encoding='utf-8') as f:
        if p.suffix.lower() in ['.yaml', '.yml']:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    return Brief(**data)

def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)

def ratio_to_folder(ratio: str) -> str:
    return ratio.replace(':', 'x')

def save_json(path: str | Path, data: Dict[str, Any]):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def save_csv(path: str | Path, rows: list[dict[str, Any]]):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with open(p, 'w', newline='', encoding='utf-8') as f:
            f.write('')
        return
    fieldnames = list(rows[0].keys())
    with open(p, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
