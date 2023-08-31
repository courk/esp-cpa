"""Configuration file for ESP32C6, first round, SEC_DPA enabled."""
import numpy as np

n_groups = 2


def selector(x: np.array) -> np.array:
    """Select traces based on guessed crypto clock behavior."""
    first_cycle_en = x[:, :, 347 - 24] > 145
    second_cycle_en = x[:, :, 347] > 147
    third_cycle_en = x[:, :, 347 + 24] > 115

    conditions = [
        first_cycle_en & second_cycle_en,
        np.logical_not(first_cycle_en) & second_cycle_en & third_cycle_en,
        first_cycle_en & np.logical_not(second_cycle_en) & third_cycle_en,
    ]
    return np.select(conditions, choicelist=[0, 1, 1], default=-1)


# Pre-processing filter parameters
f_type = "band"
f_order = 8
f_cutoff = (
    0.35e6,
    0.80e6,
)
