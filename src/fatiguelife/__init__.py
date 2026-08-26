"""FatigueLife: educational fatigue-life estimation for cantilever brackets."""

__version__ = "0.1.0"

SCOPE_STATEMENT = (
    "This is an educational comparative model. It uses simplified beam theory, "
    "Basquin S-N fatigue curves, Modified Goodman mean-stress correction, and a "
    "simplified notch factor. It does not provide certified component-life "
    "predictions or replace experimental fatigue testing."
)

MATERIAL_NOTICE = (
    "Fatigue properties are condition-specific. Results depend on the selected "
    "dataset and may not apply to a real component."
)
