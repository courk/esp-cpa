"""Configuration file for ESP32C3, second round."""

from binascii import unhexlify

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
model = "round1dectable"
model_beta_modifier = 2e-2
model_args = {"tk0": unhexlify("2f5395410f892e12d69c2cb73256ce1d")}
