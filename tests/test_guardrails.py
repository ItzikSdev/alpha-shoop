"""Tests: Kill-switch and Pydantic validator guardrails."""
import pytest
from src.guardrails.kill_switch import KillSwitch
from src.guardrails.validator import GuardrailValidator
from pydantic import BaseModel


def test_kill_switch_inactive_by_default():
    ks = KillSwitch()
    assert ks.is_active is False


def test_kill_switch_activate():
    ks = KillSwitch()
    ks.activate(reason="budget exceeded", operator="test")
    assert ks.is_active is True
    assert ks.state["reason"] == "budget exceeded"


def test_kill_switch_reset():
    ks = KillSwitch()
    ks.activate(reason="test", operator="test")
    ks.reset(operator="admin")
    assert ks.is_active is False


def test_kill_switch_spend_under_limit():
    ks = KillSwitch()
    ks.record_spend(100.0, 500.0)   # fine
    assert ks.is_active is False


def test_kill_switch_spend_over_limit():
    ks = KillSwitch()
    with pytest.raises(ValueError, match="limit"):
        ks.record_spend(600.0, 500.0)
    assert ks.is_active is True


def test_kill_switch_accumulates_across_calls():
    ks = KillSwitch()
    ks.record_spend(300.0, 500.0)
    with pytest.raises(ValueError):
        ks.record_spend(250.0, 500.0)


class _SampleInput(BaseModel):
    query: str
    count: int


def test_validator_valid_input():
    result = GuardrailValidator.validate_input(_SampleInput, {"query": "shoes", "count": 5})
    assert result.query == "shoes"
    assert result.count == 5


def test_validator_invalid_input_raises():
    with pytest.raises(ValueError, match="Input validation failed"):
        GuardrailValidator.validate_input(_SampleInput, {"query": "shoes"})  # missing count


def test_validator_wrong_type_raises():
    with pytest.raises(ValueError, match="Input validation failed"):
        GuardrailValidator.validate_input(_SampleInput, {"query": "shoes", "count": "not-a-number"})
