"""Configuration file for ESP32 round 0."""

# Pre-processing filter parameters
f_type = "low"
f_order = 8
f_cutoff = (0.8e6,)
drift_compensation = False

# POI selection
poi = [152]

# Leakage model
model = "round0"
model_beta_modifier = 1.0
model_args = None
