"""Cyclic end load P(t) = Pm + Pa*sin(omega*t).

Frequency is displayed for context only; constant-amplitude stress-life
modelling is frequency-independent.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Loading:
    alternating_load_n: float
    mean_load_n: float
    frequency_hz: float = 0.0

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if self.alternating_load_n < 0.0:
            errors.append(
                "Alternating load Pa must be non-negative; got "
                f"{self.alternating_load_n:.3g} N."
            )
        return errors
