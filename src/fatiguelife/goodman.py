"""Modified Goodman mean-stress correction.

A simplified screening criterion, not a general mean-stress model. For
compressive local mean stress the denominator is capped at 1, i.e. no
beneficial credit is taken for compressive mean stress.
"""


class GoodmanInvalidError(ValueError):
    """Raised when sigma_m_local >= Sut and the correction is undefined."""


def equivalent_fully_reversed_pa(
    sigma_a_local_pa: float, sigma_m_local_pa: float, sut_pa: float
) -> float:
    """sigma_a_eq = sigma_a_local / (1 - sigma_m_local/Sut), capped for compression."""
    if sigma_m_local_pa >= sut_pa:
        raise GoodmanInvalidError(
            "Local mean stress is at or above the ultimate strength; the "
            "Modified Goodman correction is invalid and no fatigue prediction "
            "is available."
        )
    denominator = 1.0 - sigma_m_local_pa / sut_pa
    if denominator > 1.0:  # compressive mean stress: take no credit
        denominator = 1.0
    return sigma_a_local_pa / denominator
