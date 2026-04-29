"""Tests for English-band rendering of BeliefState into prompt text."""
from __future__ import annotations

from simswarm.llm import render_beliefs
from simswarm.types import BeliefState


def test_strong_positive_renders_as_strongly_supportive():
    bs = BeliefState(positions={"AI regulation": 0.85},
                     confidence={"AI regulation": 0.9})
    text = render_beliefs(bs)
    assert "strongly supportive" in text.lower()
    assert "AI regulation" in text


def test_neutral_position_renders_as_undecided():
    bs = BeliefState(positions={"climate": 0.05}, confidence={"climate": 0.1})
    text = render_beliefs(bs)
    assert "undecided" in text.lower() or "neutral" in text.lower()


def test_high_confidence_renders_as_firmly_held():
    bs = BeliefState(positions={"trade": 0.5}, confidence={"trade": 0.95})
    text = render_beliefs(bs)
    lowered = text.lower()
    assert "firmly held" in lowered or "strongly held" in lowered


def test_low_confidence_renders_as_open_to_change():
    bs = BeliefState(positions={"trade": 0.5}, confidence={"trade": 0.1})
    text = render_beliefs(bs)
    assert "open" in text.lower() or "uncertain" in text.lower()


def test_empty_beliefs_returns_empty_string():
    assert render_beliefs(BeliefState()) == ""


def test_multiple_topics_each_get_a_line():
    bs = BeliefState(
        positions={"a": 0.8, "b": -0.6},
        confidence={"a": 0.5, "b": 0.5},
    )
    text = render_beliefs(bs)
    assert "a" in text and "b" in text
    assert text.count("\n") >= 1
