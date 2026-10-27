"""Metric primitives: quantiles, WER, entity policies. No value defaults to 0."""

from voiceos.benchmark.dataset import Entities
from voiceos.benchmark.metrics import nearest_rank, score_entities, summarize_ms, word_error_rate


def test_nearest_rank() -> None:
    values = [float(v) for v in range(1, 101)]
    assert nearest_rank(values, 0.5) == 50
    assert nearest_rank(values, 0.95) == 95
    assert nearest_rank([7.0], 0.95) == 7
    assert nearest_rank([], 0.5) is None


def test_summary_of_nothing_is_null_not_zero() -> None:
    assert summarize_ms([]) == {"n": 0, "p50": None, "p95": None, "max": None}
    assert summarize_ms([1_000_000, 3_000_000])["max"] == 3.0


def test_word_error_rate() -> None:
    assert word_error_rate("Am 23.10. um 9 Uhr", "am 23.10. um 9 uhr") == (0, 5)
    assert word_error_rate("eins zwei drei", "eins drei") == (1, 3)
    assert word_error_rate("eins", "eins zwei") == (1, 1)


def test_phone_policy_is_exact_digit_sequence() -> None:
    e = Entities(phone="+49300001001")
    assert score_entities(e, "Nummer +49 30 0001001") == {"phone": True}
    assert score_entities(e, "Nummer +49 30 0001007") == {"phone": False}


def test_email_policy_exact_local_part_case_insensitive_domain() -> None:
    e = Entities(email="Max.Test@example.org")
    assert score_entities(e, "Max.Test@EXAMPLE.org.") == {"email": True}
    assert score_entities(e, "max.test@example.org") == {"email": False}


def test_names_are_not_umlaut_folded() -> None:
    e = Entities(first_name="Jürgen", last_name="Prüfling")
    assert score_entities(e, "Jürgen Prüfling") == {"first_name": True, "last_name": True}
    assert score_entities(e, "Juergen Pruefling") == {"first_name": False, "last_name": False}


def test_address_fields_scored_separately_and_postal_code_keeps_leading_zero() -> None:
    e = Entities(street="Beispielweg", house_number="3a", postal_code="01067", city="Probedorf")
    scores = score_entities(e, "Beispielweg 3a, 1067 Probedorf")
    assert scores == {"street": True, "house_number": True, "postal_code": False, "city": True}


def test_datetime_and_money() -> None:
    e = Entities(date="2026-10-23", time="09:00", amount_minor=149950, currency="EUR")
    scores = score_entities(e, "Am 23.10.2026 um 09:00, Budget 1.499,50 Euro")
    assert scores == {"date": True, "time": True, "amount": True}
    assert score_entities(Entities(amount_minor=80000), "achthundert Euro") == {"amount": False}
