"""Arabic output clean-up (Milestone G2).

Deterministic fixes applied to every AI answer after it arrives, so small model slips
never reach the operator:
  - Arabic-Indic / Persian digits -> Western digits (HMI rule: always 0-9)
  - known wrong farm terms -> the agreed term (e.g. evapotranspiration = التبخر-نتح)
"""

import re
from typing import Any

from pydantic import BaseModel

from app.services.ai.purity import strip_glosses

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# wrong / inconsistent phrase -> agreed term
_TERMS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"التبخر\s*(?:و|-)?\s*(?:التعرق|النتح|التنفس)"), "التبخر-نتح"),
    (re.compile(r"البخر\s*(?:و|-)?\s*نتح"), "التبخر-نتح"),
    (re.compile(r"مضخة\s+(?:الدفع|الداعم|التقويه)"), "مضخة التعزيز"),
    (re.compile(r"الصمامات\s+الكهربائية\s+الملفية"), "الصمامات الكهربائية"),
]
# Arabic decimal separator between digits -> "."
_DECIMAL = re.compile(r"(?<=\d)٫(?=\d)")


def normalize_text(text: str) -> str:
    if not text:
        return text
    out = text.translate(_DIGITS)
    out = _DECIMAL.sub(".", out)
    out = strip_glosses(out)
    for pattern, repl in _TERMS:
        out = pattern.sub(repl, out)
    return out


def normalize_output(obj: Any) -> Any:
    """Normalize every string (and list of strings) field of a pydantic model in place."""
    if not isinstance(obj, BaseModel):
        return obj
    for name in type(obj).model_fields:
        val = getattr(obj, name, None)
        if isinstance(val, str):
            setattr(obj, name, normalize_text(val))
        elif isinstance(val, list):
            setattr(
                obj,
                name,
                [normalize_text(v) if isinstance(v, str) else normalize_output(v) for v in val],
            )
        elif isinstance(val, BaseModel):
            normalize_output(val)
    return obj
