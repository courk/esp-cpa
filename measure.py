#!/usr/bin/env python3
"""Gather traces with the EspCpaBoard."""

import binascii
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import cpa_lib
import numpy as np
import rich.progress
import typer
import zarr
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from typing_extensions import Annotated

from esp_cpa_board import (
    EspCpaBoard,
    LiveSignalViewer,
    SignalPreprocessor,
    TempMonitorThread,
    load_config,
)

app = typer.Typer()


class LiveKeyRanker:
    """Perform live key ranking."""

    def __init__(self, key: bytes, config: Dict[str, Any]) -> None:
        """Instantiate a LiveKeyRanker object.

        Args:
            key (bytes): The known AES round key to use for the ranking
            config: Configuration data for signal preprocessing
        """
        self._key = key

        self._samples_preprocessor = SignalPreprocessor(config)

        self._solvers = [
            cpa_lib.CpaSolver(
                config["model"], i, config["model_beta_modifier"], config["model_args"]
            )
            for i in range(16)
        ]

        self._payloads: list[bytes] = []
        self._samples: list[np.ndarray] = []

        self._config = config

    def feed(self, payload: bytes, samples: np.ndarray) -> None:
        """Feed samples.

        Args:
            payload (bytes): The input payload.
            samples (np.ndarray): The samples.
        """
        self._payloads.append(payload[::-1])  # Reversed order
        self._samples.append(samples)

    def get_key_ranks(self) -> List[int]:
        """Get the key ranks, based on the past samples.

        Returns:
            (List[int]): A list of key ranks, a list of best timestamps
        """
        samples = np.array(self._samples, float)
        samples = self._samples_preprocessor.process(samples)

        rank_result = []
        for i, s in enumerate(self._solvers):
            s.update(self._payloads, samples)
            mat = s.get_result()
            rank = self._compute_key_rank(i, mat)
            rank_result.append(rank)

        self._payloads = []
        self._samples = []

        return rank_result

    def _compute_key_rank(self, i: int, mat: np.ndarray) -> int:
        """Compute the key rank at the give index.

        Args:
            i (int): The index
            mat (np.ndarray): The correlation matrix

        Returns:
            int: The key rank
        """
        mat = np.abs(mat)
        sorted_guesses = []
        for _ in range(256):
            index_max = np.argmax(mat)
            b, t = np.unravel_index(index_max, mat.shape)
            sorted_guesses.append(b)
            mat[b] = 0
        return sorted_guesses.index(self._key[i])


class MeasurementSpeedColumn(ProgressColumn):
    """Renders human readable measurement speed."""

    def render(self, task: rich.progress.Task) -> rich.progress.Text:
        """Show measurement speed."""
        speed = task.finished_speed or task.speed
        if speed is None:
            return rich.progress.Text("?", style="progress.data.speed")
        return rich.progress.Text(f"{speed:0.1f} m/s", style="progress.data.speed")


progress = Progress(
    BarColumn(bar_width=None),
    TaskProgressColumn(),
    "•",
    TimeRemainingColumn(),
    "•",
    MofNCompleteColumn(),
    "•",
    MeasurementSpeedColumn(),
)


@app.command()
def main(
    measurement_config_filename: Path,
    output_filename: Path,
    key: Annotated[
        Optional[str],
        typer.Option(help="The key, if known, to compute live key ranking"),
    ] = None,
    analysis_config_filename: Annotated[
        Optional[Path],
        typer.Option(help="The configuration file to use for live key ranking"),
    ] = None,
    gui_display: bool = False,
) -> None:
    """Perform a measurement campaign."""
    measurement_config = load_config(measurement_config_filename)

    if key is not None:
        try:
            raw_key = binascii.unhexlify(key)
        except binascii.Error:
            raise typer.BadParameter("Invalid key format")
        if len(raw_key) != 16:
            raise typer.BadParameter("The size of the key is expected to be 16 bytes")
        if analysis_config_filename is not None:
            live_key_ranker = LiveKeyRanker(
                raw_key, load_config(analysis_config_filename)
            )
        else:
            raise typer.BadParameter("Missing analysis configuration")
    else:
        live_key_ranker = None

    if gui_display:
        live_signal_viewer = LiveSignalViewer()
    else:
        live_signal_viewer = None

    board = EspCpaBoard(measurement_config)

    board.connect()
    board.set_dut_power(True)
    board.set_clk_en(True)
    board.set_amplifier_gain(measurement_config["amplifier_gain"])

    temp_monitor_args: Dict[str, Any] = {}

    if measurement_config["dut_temperature"] is not None:
        temp_monitor_args["target_temperature"] = measurement_config["dut_temperature"]

    if live_signal_viewer is not None:
        temp_monitor_args["callback"] = live_signal_viewer.add_temperature

    temperature_thread = TempMonitorThread(board, **temp_monitor_args)
    temperature_thread.start()

    try:
        sync_step = 5000  # Compute live key ranks each sync_step samples
        temp_rate = 100  # Record a temperature data point each temp_rate sample
        with zarr.open(output_filename, "w-") as output_f:
            samples_array = output_f.create_dataset(
                "samples",
                shape=(
                    0,
                    measurement_config["averaging"],
                    measurement_config["n_samples"],
                ),
                dtype="i2",
                chunks=(
                    sync_step,
                    measurement_config["averaging"],
                    measurement_config["n_samples"],
                ),
            )
            payloads_array = output_f.create_dataset(
                "payloads",
                shape=(0, 16),
                chunks=(sync_step, 16),
                dtype="u1",
                compressor=None,  # Compressing random data is wasteful
            )
            temperatures_array = output_f.create_dataset(
                "temperatures",
                shape=(0,),
                chunks=(sync_step // temp_rate,),
                dtype="f",
            )

            samples_chunk = np.zeros(
                shape=(
                    sync_step,
                    measurement_config["averaging"],
                    measurement_config["n_samples"],
                ),
                dtype=np.int16,
            )
            payloads_chunk = np.zeros(shape=(sync_step, 16), dtype=np.uint8)

            with progress:
                for i in progress.track(range(measurement_config["n_measurements"])):
                    payload = random.randbytes(16)

                    board.set_flash_payload(payload)

                    samples = board.perform_measurement(
                        n_samples=measurement_config["n_samples"],
                        n_measurements=measurement_config["averaging"],
                    )
                    assert samples.shape == (
                        measurement_config["averaging"],
                        measurement_config["n_samples"],
                    ), f"Invalid number of samples ({samples.shape})"

                    samples_chunk[i % sync_step] = samples
                    payloads_chunk[i % sync_step] = [n for n in payload]

                    # Fill temperature buffer
                    if i % temp_rate == 0:
                        temp = temperature_thread.get_temp()
                        if temp is not None:
                            temperatures_array.append((temp,))

                    # Fill zarr buffers
                    if (i + 1) % sync_step == 0:
                        samples_array.append(samples_chunk)
                        payloads_array.append(payloads_chunk)

                    if live_key_ranker is not None:
                        live_key_ranker.feed(payload, samples)
                        if (i + 1) % sync_step == 0:
                            ranks = live_key_ranker.get_key_ranks()
                            average_rank = np.mean(ranks)
                            progress.console.print(
                                f"Average rank = {average_rank:0.1f}"
                            )
                            progress.console.print(f"    {ranks}")
                            if live_signal_viewer:
                                live_signal_viewer.add_ranking(average_rank)

                    if live_signal_viewer is not None:
                        live_signal_viewer.feed(np.mean(samples, axis=0))

    except KeyboardInterrupt:
        pass

    temperature_thread.stop()
    board.set_clk_en(False)
    board.set_dut_power(False)


if __name__ == "__main__":
    app()
