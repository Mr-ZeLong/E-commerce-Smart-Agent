import pytest

from app.evaluation.token_efficiency import token_efficiency


def test_token_efficiency_normal_case():
    assert token_efficiency(100, 100) == pytest.approx(0.5)


def test_token_efficiency_high_input():
    assert token_efficiency(900, 100) == pytest.approx(0.9)


def test_token_efficiency_high_output():
    assert token_efficiency(100, 900) == pytest.approx(0.1)


def test_token_efficiency_only_input():
    assert token_efficiency(100, 0) == pytest.approx(1.0)


def test_token_efficiency_only_output():
    assert token_efficiency(0, 100) == pytest.approx(0.0)


def test_token_efficiency_zero_total():
    assert token_efficiency(0, 0) == 0.0


def test_token_efficiency_negative_input():
    assert token_efficiency(-10, 100) == 0.0


def test_token_efficiency_negative_output():
    assert token_efficiency(100, -10) == 0.0
