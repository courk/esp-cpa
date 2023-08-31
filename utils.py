#!/usr/bin/env python3
"""Misc utils."""

from pathlib import Path
from typing import List

import typer
import zarr

app = typer.Typer()


@app.command()
def fuse(
    input_filenames: List[Path],
    output_filename: Path,
) -> None:
    """Fuse multiple datafiles into one."""
    zarr_files = [zarr.open(f, "r") for f in input_filenames]

    _, averaging, n_samples = zarr_files[0]["samples"].shape

    sync_step = 5000  # Compute live key ranks each sync_step samples
    temp_rate = 100  # Record a temperature data point each temp_rate sample
    with zarr.open(output_filename, "w-") as output_f:
        samples_array = output_f.create_dataset(
            "samples",
            shape=(
                0,
                averaging,
                n_samples,
            ),
            dtype="i2",
            chunks=(
                sync_step,
                averaging,
                n_samples,
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

        for source in zarr_files:
            for i in range(0, source["samples"].shape[0], sync_step):
                samples_array.append(source["samples"][i : i + sync_step])
                payloads_array.append(source["payloads"][i : i + sync_step])

            assert (
                samples_array.shape[0] == payloads_array.shape[0]
            ), "samples / payload count mismatch"

            for i in range(0, source["temperatures"].shape[0], sync_step // temp_rate):
                temperatures_array.append(source["temperatures"][i : i + sync_step])


@app.command()
def info(
    data_filename: Path,
) -> None:
    """Display information regarding captured power traces."""
    data = zarr.open(data_filename, "r")
    n_cycles, averaging, n_samples = data["samples"].shape
    print(f"{n_cycles = }")
    print(f"{averaging = }")
    print(f"{n_samples = }")


if __name__ == "__main__":
    app()
