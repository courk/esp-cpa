"""Configuration file for ESP32C6, first round."""


# Pre-processing filter parameters
f_type = "band"
f_order = 8
f_cutoff = (
    0.35e6,
    0.80e6,
)
drift_compensation = True

# POI selection
poi = [345]

# Leakage model
model = "round0dectable"
model_beta_modifier = 2e-2
model_args = None
