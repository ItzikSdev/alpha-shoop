"""Pydantic I/O validator — all agent inputs and outputs pass through here."""
from __future__ import annotations
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar

M = TypeVar("M", bound=BaseModel)


class GuardrailValidator:
    """
    Wraps every agent tool call with strict Pydantic validation.
    Raises ValueError with structured error details on schema mismatch.
    """

    @staticmethod
    def validate_input(model: Type[M], data: dict) -> M:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Input validation failed: {exc.error_count()} error(s)\n{exc}") from exc

    @staticmethod
    def validate_output(model: Type[M], data: dict) -> M:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Output validation failed: {exc.error_count()} error(s)\n{exc}") from exc
