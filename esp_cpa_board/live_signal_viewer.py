#!/usr/bin/env python3
"""GUI live viewer of the captured signals."""

import time

import numpy as np
import pyqtgraph as pg
import pyqtgraph.multiprocess as mp

__all__ = ["LiveSignalViewer"]


class LiveSignalViewer:
    """GUI live viewer of the captured signals."""

    def __init__(self, rate_limit=0.1) -> None:
        """Instantiate a Live Viewer instance.

        Args:
            rate_limit (float, optional): Maximum refresh period, expressed in seconds. Defaults to 0.1.
        """
        pg.mkQApp()

        self._gui_proc = mp.QtProcess()

        rpg = self._gui_proc._import("pyqtgraph")
        rpg.setConfigOptions(antialias=True)

        self._layout = rpg.GraphicsLayoutWidget(show=True, title="Live Signal Viewer")

        trace_plot = self._layout.addPlot(
            title="Current Trace", row=1, col=0, colspan=2
        )
        self._trace_curve = trace_plot.plot(pen="y")
        trace_plot.setYRange(-300, 300, padding=0.2)
        trace_plot.showGrid(x=True, y=True)

        ranking_plot = self._layout.addPlot(title="Average Ranking", row=2, col=0)
        self._ranking_curve = ranking_plot.plot(pen="y")
        ranking_plot.showGrid(x=True, y=True)
        self._ranks: list[float] = []

        temperature_plot = self._layout.addPlot(title="DUT Temperature", row=2, col=1)
        self._temperature_curve = temperature_plot.plot(pen="y")
        temperature_plot.showGrid(x=True, y=True)
        temperature_plot.setXRange(0, 500, padding=0.2)
        self._temperatures: list[float] = []

        self._last_update = time.time()
        self._rate_limit = rate_limit

    def add_ranking(self, rank: float) -> None:
        """Add a ranking point to the graph.

        Args:
            rank (float): The ranking point to add
        """
        self._ranks.append(rank)
        t_data = self._gui_proc.transfer(self._ranks)
        self._ranking_curve.setData(y=t_data, _callSync="off")

    def add_temperature(self, temperature: float) -> None:
        """Add a temperature point to the graph.

        Args:
            temperature (float): The temperature point to add
        """
        if len(self._temperatures) > 500:
            self._temperatures = []
        self._temperatures.append(temperature)
        t_data = self._gui_proc.transfer(self._temperatures)
        self._temperature_curve.setData(y=t_data, _callSync="off")

    def feed(self, samples: np.ndarray) -> None:
        """Feed samples.

        Args:
            samples (np.ndarray): The samples.
        """
        t = time.time()
        if t - self._last_update > self._rate_limit:
            t_data = self._gui_proc.transfer(samples)
            self._trace_curve.setData(y=t_data, _callSync="off")
            self._last_update = t
