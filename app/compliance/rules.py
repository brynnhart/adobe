from __future__ import annotations
import json, os, re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_RULES_PATH = Path("config/compliance_rules.json")
RULES_ENV = "COMPLIANCE_RULES_PATH"
SANITIZE_ENV = "COMPLIANCE_SANITIZE"  # "1" to auto-replace

@dataclass
class ComplianceRules:
    prohibited_terms: List[str]
    replacements: Dict[str, str]

    @classmethod
    def load(cls) -> "ComplianceRules":
        """
        Load compliance rules from COMPLIANCE_RULES_PATH or default JSON file.
        """
        p = os.getenv(RULES_ENV)
        path = Path(p) if p else DEFAULT_RULES_PATH
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(
                    prohibited_terms=data.get("prohibited_terms", []),
                    replacements=data.get("replacements", {}),
                )
            except Exception as e:
                print(f"[WARN] Failed to load compliance rules ({e}); using empty set.")
        return cls([], {})

def _find_terms(text: str, terms: List[str]) -> List[str]:
    low = text.lower()
    return [t for t in terms if t.lower() in low]

def check_message(text: str, rules: ComplianceRules) -> Tuple[str, List[str], bool]:
    """
    Returns (possibly_modified_text, offending_terms, modified_flag)
    """
    offending = _find_terms(text or "", rules.prohibited_terms)
    if not offending:
        return text, [], False

    sanitize = os.getenv(SANITIZE_ENV, "0").lower() in ("1", "true", "yes")
    if not sanitize or not rules.replacements:
        return text, offending, False

    new = text
    for term in offending:
        repl = rules.replacements.get(term.lower())
        if not repl:
            continue
        new = re.sub(re.escape(term), repl, new, flags=re.IGNORECASE)

    remaining = _find_terms(new, rules.prohibited_terms)
    modified = new != text
    return new, remaining, modified
