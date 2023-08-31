#!/usr/bin/env python3
"""Misc utilities."""


from pathlib import Path
from typing import Any, Dict

import numpy as np
from scipy import signal


def load_config(filename: Path) -> Dict[str, Any]:
    """Load configuration variables.

    Args:
        filename (Path): The configuration file to load

    Returns:
        Dict[str, Any]: The configuration data
    """
    config: Dict[str, Any] = {}
    exec(filename.read_text(), None, config)
    return config


class SignalPreprocessor:
    """Traces pre-processor."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the SignalPreprocessor object with a configuration dictionary.

        Args:
            config: A dictionary containing the configuration parameters.
        """
        if config["f_type"] is not None:
            self._f_b, self._f_a = signal.butter(
                config["f_order"], config["f_cutoff"], fs=12e6, btype=config["f_type"]
            )

        self._config = config

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Pre-process a captured trace.

        Args:
            samples (np.ndarray): The captured samples

        Returns:
            np.ndarray: The processed samples
        """
        samples = np.mean(samples, axis=1)

        if self._config["f_type"] is not None:
            samples = signal.filtfilt(self._f_b, self._f_a, samples, axis=1)

        # POI selection
        samples = samples[:, self._config["poi"]]

        if self._config["drift_compensation"]:
            samples -= np.mean(samples, axis=0, keepdims=True)
            samples /= np.var(samples, axis=0, keepdims=True)

        return samples
