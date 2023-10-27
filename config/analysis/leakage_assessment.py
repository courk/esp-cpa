"""Leakage assessment configuration."""
# Pre-processing filter parameters
f_type = "band"
f_order = 8
f_cutoff = (
    0.40e6,
    1.5e6,
)
drift_compensation = True

poi = range(0, 1024)
