#!/usr/bin/env python3
"""Temperature controller classes."""

import time
from threading import Thread
from typing import Callable, Optional

from .esp_cpa_board import EspCpaBoard

__all__ = ["TempController", "TempMonitorThread"]


class TempController:
    """DUT Temperature controller logic."""

    def __init__(self, setpoint: float = 35.0):
        """Initialize a PID controller for the temperature of the DUT.

        Args:
            setpoint (float): The desired setpoint for the controller. Defaults to 35°C.
        """
        self._setpoint = setpoint

        self._e = 0.0
        self._i_e = 0.0
        self._d_e = 0.0
        self._previous_e = 0.0

        self._saturating = False

        ku = 200.0
        tu = 10

        self._P = 0.6 * ku
        self._I = 1.2 * ku / tu
        self._D = 0.075 * ku * tu
        self._Ti = 0.5 * tu
        self._Td = 0.125 * tu

    def regulate(self, temperature: float) -> int:
        """Regulate the temperature using a PID controller.

        Args:
            temperature (float): The current temperature.

        Returns:
            int: The PWM value to regulate the temperature.
        """
        self._e = self._setpoint - temperature
        if not self._saturating:  # Anti-Windup
            self._i_e += self._e
        self._d_e = self._e - self._previous_e
        self._previous_e = self._e

        pwm = self._P * (self._e + 1.0 / self._Ti * self._i_e + self._Td * self._d_e)
        pwm = round(pwm)

        if pwm > 255:
            pwm = 255
            self._saturating = True
        elif pwm < 0:
            self._saturating = True
            pwm = 0
        else:
            self._saturating = False

        return pwm


class TempMonitorThread(Thread):
    """Temperature monitoring and control thread."""

    def __init__(
        self,
        esp_cpa_board: EspCpaBoard,
        target_temperature: Optional[float] = None,
        callback: Optional[Callable] = None,
    ) -> None:
        """Instantiate a temperature controller thread.

        Args:
            esp_cpa_board (EspCpaBoard): An instance of an EspCpaBoard object
            target_temperature (Optional[float]): Optionally regulate the DUT temperature to this value, expressed in °C. Defaults to None.
            callback (Optional[Callable], optional): Callback to call for each new temperature value. Defaults to None.
        """
        super().__init__()
        self._controller: Optional[TempController] = None
        if target_temperature is not None:
            self._controller = TempController(target_temperature)
        self._board = esp_cpa_board
        self._callback = callback

        self._last_temp: Optional[float] = None

        self._running = False

    def run(self) -> None:
        self._running = True

        while self._running:
            self._last_temp = temp = self._board.get_temperature()

            if self._controller is not None:
                pwm = self._controller.regulate(temp)
                self._board.set_heater_pwm(pwm)

            if self._callback is not None:
                self._callback(temp)
            time.sleep(0.1)

        self._board.set_heater_pwm(0)

    def stop(self) -> None:
        """Stop the temperature control thread."""
        self._running = False

    def get_temp(self) -> Optional[float]:
        """Get the last recorded temperature value.

        Returns:
            Optional[float]: The measured temmperature, expressed in °C or None if the temperature has not been sampled yet.
        """
        return self._last_temp
