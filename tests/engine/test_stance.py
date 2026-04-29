"""VADER-based stance scoring tests."""
from __future__ import annotations

from simswarm.stance import score_stance


def test_clearly_positive_returns_positive():
    assert score_stance("This is wonderful, I love it") > 0.3


def test_clearly_negative_returns_negative():
    assert score_stance("This is terrible, I hate it") < -0.3


def test_negation_inverts_polarity():
    """VADER handles 'not' correctly; the keyword bag did not."""
    assert score_stance("This is not good") < 0.0
    assert score_stance("This is not bad") > 0.0


def test_intensifiers_boost_magnitude():
    """VADER distinguishes 'good' from 'extremely good'."""
    mild = score_stance("This is good")
    strong = score_stance("This is absolutely amazing")
    assert strong > mild


def test_neutral_returns_near_zero():
    assert abs(score_stance("The meeting is at three o'clock")) < 0.2


def test_empty_string_returns_zero():
    assert score_stance("") == 0.0


def test_score_in_range():
    assert -1.0 <= score_stance("anything") <= 1.0
