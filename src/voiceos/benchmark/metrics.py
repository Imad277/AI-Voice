"""Metric primitives. Missing data stays ``None``; nothing defaults to 0."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence

from voiceos.benchmark.dataset import Entities


def nearest_rank(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank quantile (q in (0, 1]); None for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def summarize_ms(values_ns: Sequence[int]) -> dict[str, float | int | None]:
    ms = [v / 1_000_000 for v in values_ns]
    return {
        "n": len(ms),
        "p50": nearest_rank(ms, 0.50),
        "p95": nearest_rank(ms, 0.95),
        "max": max(ms) if ms else None,
    }


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower()
    return re.findall(r"[\w@.+'-]+", text)


def word_error_rate(reference: str, hypothesis: str) -> tuple[int, int]:
    """(edit distance in words, reference word count). Rate = errors / words."""
    ref, hyp = _words(reference), _words(hypothesis)
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1], len(ref)


# Entity policies (Phase-1-lite, documented in docs/benchmark/BENCHMARK_METHOD.md):
# names NFC, case-sensitive, no umlaut folding; phone exact digit sequence; email exact local
# part, case-insensitive domain; postal code as string; money in integer minor units.


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _phone_ok(expected: str, hypothesis: str) -> bool:
    return _digits(expected) in _digits(hypothesis)


def _email_ok(expected: str, hypothesis: str) -> bool:
    local, _, domain = expected.partition("@")
    for token in re.findall(r"[^\s,;]+@[^\s,;]+", hypothesis):
        h_local, _, h_domain = token.rstrip(".").partition("@")
        if h_local == local and h_domain.lower() == domain.lower():
            return True
    return False


def _text_ok(expected: str, hypothesis: str) -> bool:
    return unicodedata.normalize("NFC", expected) in unicodedata.normalize("NFC", hypothesis)


def _amount_ok(expected_minor: int, hypothesis: str) -> bool:
    for match in re.findall(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?", hypothesis):
        euros, _, cents = match.replace(".", "").partition(",")
        if int(euros) * 100 + int(cents or 0) == expected_minor:
            return True
    return False


_MONTHS = [
    "januar",
    "februar",
    "märz",
    "april",
    "mai",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "dezember",
]


def _date_ok(expected: str, hypothesis: str) -> bool:
    """dd.mm.(yyyy) or 'dd. <Monat> (yyyy)'; day without leading zero allowed."""
    year, month, day = expected.split("-")
    text = unicodedata.normalize("NFC", hypothesis).lower()
    d, m = str(int(day)), str(int(month))
    numeric = rf"\b0?{d}\.\s?0?{m}\.(\s?{year})?"
    named = rf"\b0?{d}\.?\s+{_MONTHS[int(month) - 1]}(\s+{year})?\b"
    return re.search(numeric, text) is not None or re.search(named, text) is not None


def _time_ok(expected: str, hypothesis: str) -> bool:
    """HH:MM, HH.MM or 'HH Uhr MM' (minutes may be omitted only when 00)."""
    hours, minutes = (int(x) for x in expected.split(":"))
    text = hypothesis.lower()
    patterns = [rf"\b0?{hours}[:.]{minutes:02d}\b", rf"\b0?{hours}\s*uhr\s*{minutes}\b"]
    if minutes == 0:
        patterns.append(rf"\b0?{hours}\s*uhr\b")
    return any(re.search(p, text) for p in patterns)


def last_number(hypothesis: str) -> str | None:
    numbers = re.findall(r"\d+", hypothesis)
    return numbers[-1] if numbers else None


def score_entities(expected: Entities, hypothesis: str) -> dict[str, bool]:
    """Per-field correctness for every field present in the expected entities."""
    scores: dict[str, bool] = {}
    for field in ("first_name", "last_name", "street", "city"):
        value = getattr(expected, field)
        if value is not None:
            scores[field] = _text_ok(value, hypothesis)
    if expected.house_number is not None:
        scores["house_number"] = (
            re.search(
                rf"(?<![\w]){re.escape(expected.house_number)}(?![\w])", hypothesis, re.IGNORECASE
            )
            is not None
        )
    if expected.postal_code is not None:  # digit sequence; leading zeros must survive
        scores["postal_code"] = expected.postal_code in _digits(hypothesis)
    if expected.phone is not None:
        scores["phone"] = _phone_ok(expected.phone, hypothesis)
    if expected.email is not None:
        scores["email"] = _email_ok(expected.email, hypothesis)
    if expected.date is not None:
        scores["date"] = _date_ok(expected.date, hypothesis)
    if expected.time is not None:
        scores["time"] = _time_ok(expected.time, hypothesis)
    if expected.amount_minor is not None:
        scores["amount"] = _amount_ok(expected.amount_minor, hypothesis)
    return scores
