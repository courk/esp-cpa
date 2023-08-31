"""Configuration file for ESP32 round 1."""
from binascii import unhexlify

# Pre-processing filter parameters
f_type = "low"
f_order = 8
f_cutoff = (0.8e6,)
drift_compensation = True

# POI selection
poi = [180]

# Leakage model
model = "round1"
model_beta_modifier = 1.0
model_args = {"k0": unhexlify("e69435d796492f8c461a64c6a34bc91c")}
