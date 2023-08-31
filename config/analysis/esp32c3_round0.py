"""Configuration file for ESP32C3, first round."""


# Pre-processing filter parameters
f_type = "band"
f_order = 8
f_cutoff = (
    0.40e6,
    0.90e6,
)
drift_compensation = True

# POI selection
poi = [480]

# Leakage model
model = "round0dectable"
model_beta_modifier = 0.19
model_args = None
