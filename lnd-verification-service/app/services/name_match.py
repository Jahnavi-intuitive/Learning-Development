"""
The name-match guardrail (FR-3.2): does the name on the credential page
match the employee who submitted it?

Uses difflib from the standard library so there's zero extra dependency to
get a working guardrail on day one. If false-positive/negative rates in the
exception queue (KPI: auto-verification rate, Section 15) suggest you need
smarter matching (nicknames, transliteration, middle-name handling), swap
this for a library like `rapidfuzz` -- the call sites don't need to change.
"""
import difflib
import re


def _normalize(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z\s]", "", name)   # drop punctuation/initials markers
    name = re.sub(r"\s+", " ", name)
    return name


def match_score(name_a: str, name_b: str) -> float:
    """Returns a 0-1 similarity score between two names."""
    a, b = _normalize(name_a), _normalize(name_b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def is_match(name_a: str, name_b: str, threshold: float) -> bool:
    return match_score(name_a, name_b) >= threshold
