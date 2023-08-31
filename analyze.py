#!/usr/bin/env python3
"""Analyze power traces."""

from binascii import unhexlify
from pathlib import Path
from typing import Annotated, List, Optional

import cpa_lib
import numpy as np
import pandas as pd
import typer
import zarr
from rich.progress import track
from scipy import signal

from esp_cpa_board import SignalPreprocessor, load_config

app = typer.Typer()


@app.command()
def extract_traces(
    data_filename: Path,
    indexes: str,
    output_filename: Path,
    analysis_filename: Optional[Path] = None,
) -> None:
    """Extract traces from a capture file."""
    data_f = zarr.open(data_filename, "r")
    samples_array = data_f["samples"]

    if analysis_filename is not None:
        config = load_config(analysis_filename)
        if config["f_type"] is not None:
            filter_b, filter_a = signal.butter(
                config["f_order"],
                config["f_cutoff"],
                fs=12e6,
                btype=config["f_type"],
            )

    dataframes = []
    for index in [int(n) for n in indexes.split(",")]:
        trace = samples_array[index, :, :]

        if analysis_filename is not None:
            if config["f_type"] is not None:
                trace = signal.filtfilt(filter_b, filter_a, trace, axis=1)

        trace = np.mean(trace, axis=0)

        df = pd.DataFrame(
            {
                "Sample Index": np.arange(0, trace.shape[0]),
                "Value": trace,
                "Name": f"Trace {index}",
            }
        )
        dataframes.append(df)

    result = pd.concat(dataframes)

    result.to_csv(output_filename)


@app.command()
def extract_spread(
    data_filename: Path,
    config_filename: Path,
    timestamp: int,
    output_filename: Path,
    start_index: Optional[int] = None,
    stop_index: Optional[int] = None,
) -> None:
    """Extract samples at a given timestamp, along with temperature readings."""
    config = load_config(config_filename)

    data_f = zarr.open(data_filename, "r")

    if start_index is None:
        start_index = 0

    if stop_index is None:
        stop_index = -1

    samples_array = data_f["samples"]
    temperature = data_f["temperatures"][: samples_array.shape[0] // 100][
        start_index // 100 : stop_index // 100
    ]
    samples_array = samples_array[start_index:stop_index,]

    temperature = np.interp(
        range(samples_array.shape[0]),
        range(0, samples_array.shape[0], 100),
        temperature,
    )

    trace = samples_array[:, :, timestamp]

    # Filtering
    trace = np.mean(trace, axis=1)

    if config["f_type"] is not None:
        filter_b, filter_a = signal.butter(
            config["f_order"],
            config["f_cutoff"],
            fs=12e6,
            btype=config["f_type"],
        )
        trace = signal.filtfilt(filter_b, filter_a, trace)

    avg_trace = np.convolve(trace, np.ones(1000), "same") / 1000

    dataframes = []

    df = pd.DataFrame(
        {
            "Measurement Index": np.arange(0, trace.shape[0]),
            "Value": trace,
            "Name": "Raw",
        }
    )
    dataframes.append(df)

    df = pd.DataFrame(
        {
            "Measurement Index": np.arange(0, trace.shape[0]),
            "Value": avg_trace,
            "Name": "Average",
        }
    )
    dataframes.append(df)

    df = pd.DataFrame(
        {
            "Measurement Index": np.arange(0, trace.shape[0]),
            "Temperature": temperature,
            "Name": "Temperature",
        }
    )
    dataframes.append(df)

    result = pd.concat(dataframes)

    result.to_csv(output_filename)


@app.command()
def compute_correlations(
    data_filename: Path,
    config_filename: Path,
    output_filename: Path,
) -> None:
    """Compute correlations values."""
    config = load_config(config_filename)
    signal_preprocessor = SignalPreprocessor(config)

    data_f = zarr.open(data_filename, "r")

    samples_array = data_f["samples"]
    payloads_array = data_f["payloads"]

    chunk_size = data_f["samples"].chunks[0]
    n_measurements = (payloads_array.shape[0] // chunk_size) * chunk_size

    n_poi_samples = len(config["poi"])

    result = zarr.open(
        output_filename,
        mode="w-",
        shape=(
            16,
            n_measurements // chunk_size,
            256,
            n_poi_samples,
        ),
        chunks=(1, 1, 256, n_poi_samples),
        dtype="f",
    )

    solvers = [
        cpa_lib.CpaSolver(
            config["model"], i, config["model_beta_modifier"], config["model_args"]
        )
        for i in range(16)
    ]

    for i in track(range(0, n_measurements, chunk_size)):
        chunk = samples_array[i : i + chunk_size][:, :, : max(config["poi"]) + 256]

        # Don't forget to flip the plaintext (ESP32 implementation detail)
        plaintext = np.flip(
            payloads_array[i : i + chunk_size],
            axis=1,
        )

        s = signal_preprocessor.process(chunk)

        # Compute correlation for each byte
        for j in range(16):
            solvers[j].update(
                plaintext,
                s,
            )
            mat = np.abs(solvers[j].get_result())
            result[j, i // chunk_size, :] = mat


@app.command()
def group_measurements(
    data_filename: Path,
    config_filename: Path,
) -> None:
    """Group measurements based on the provided configuration."""
    config = load_config(config_filename)

    data_f = zarr.open(data_filename, "r")
    samples_array = data_f["samples"]
    payloads_array = data_f["payloads"]

    if config["f_type"] is not None:
        filter_b, filter_a = signal.butter(
            config["f_order"],
            config["f_cutoff"],
            fs=12e6,
            btype=config["f_type"],
        )

    outputs = []
    for n in range(config["n_groups"]):
        o = zarr.open(f"{data_filename.stem}_group_{n}.zarr", "w-")
        o.create_dataset(
            "samples",
            shape=(
                0,
                1,
                samples_array.shape[2],
            ),
            dtype="f",
            chunks=samples_array.chunks,
        )
        o.create_dataset(
            "payloads",
            shape=(0, 16),
            chunks=payloads_array.chunks,
            dtype="u1",
            compressor=None,  # Compressing random data is wasteful
        )
        outputs.append(o)

    chunk_size = samples_array.chunks[0]

    categories_counts = {}
    categories_counts[-1] = 0
    for n in range(config["n_groups"]):
        categories_counts[n] = 0

    for i in track(range(samples_array.shape[0] // chunk_size)):
        chunk = samples_array[i * chunk_size : (i + 1) * chunk_size]
        if config["f_type"] is not None:
            f_chunk = signal.filtfilt(filter_b, filter_a, chunk, axis=2)
            categories = config["selector"](f_chunk)
        else:
            categories = config["selector"](chunk)

        selected_samples: List[List[np.ndarray]] = []
        selected_payloads: List[List[np.ndarray]] = []
        for n in range(config["n_groups"]):
            selected_samples.append([])
            selected_payloads.append([])

        for j, c in enumerate(categories):
            for n in range(config["n_groups"]):
                categories_counts[n] += np.count_nonzero(c == n)
                if any(c == n):
                    s = np.mean(chunk[j, c == n], axis=0, keepdims=True)
                    selected_samples[n].append(s)
                    selected_payloads[n].append(payloads_array[i * chunk_size + j])
            categories_counts[-1] += np.count_nonzero(c == -1)

        for n in range(config["n_groups"]):
            outputs[n]["samples"].append(selected_samples[n])
            outputs[n]["payloads"].append(selected_payloads[n])

    for n in range(config["n_groups"]):
        print(f"Group {n} has {outputs[n]['samples'].shape[0]} traces")

    total_categories_count = sum(categories_counts[n] for n in categories_counts)

    for n in categories_counts:
        count_ratio = categories_counts[n] / total_categories_count
        print(
            f"Category {n} count = {categories_counts[n]} ({count_ratio * 100.0:0.1f}%)"
        )


@app.command()
def compute_ranks(corr_filename: Path, key: str, output_filename: Path) -> None:
    """Compute key ranks, given a known round key."""
    corr = zarr.open(corr_filename, "r")

    raw_key = unhexlify(key)
    if len(raw_key) != 16:
        raise typer.BadParameter("The size of the round key is expected to be 16 bytes")

    rank_result = np.zeros((corr.shape[1], 16))

    for step in range(corr.shape[1]):
        for j, k in enumerate(raw_key):
            mat = np.array(corr[j, step])

            sorted_guesses = []

            for _ in range(256):
                index_max = np.argmax(np.abs(mat))
                b, t = np.unravel_index(index_max, mat.shape)
                sorted_guesses.append(b)
                mat[b] = 0
            rank_result[step, j] = sorted_guesses.index(k)

    avg = np.mean(rank_result[-1, :])
    print(f"Average final rank = {avg}")

    chunk_size = 5000

    dataframes = []
    for i in range(16):
        df = pd.DataFrame(
            {
                "Measurement Index": np.arange(
                    0, rank_result.shape[0] * chunk_size, chunk_size
                ),
                "Rank": rank_result[:, i],
                "Name": f"Byte {i}",
            }
        )
        dataframes.append(df)

    df = pd.DataFrame(
        {
            "Measurement Index": np.arange(
                0, rank_result.shape[0] * chunk_size, chunk_size
            ),
            "Rank": np.mean(rank_result, axis=1),
            "Name": "Average",
        }
    )
    dataframes.append(df)

    result = pd.concat(dataframes)

    result.to_csv(output_filename)


@app.command()
def find_best_poi(corr_filename: Path, key: str) -> None:
    """Find the best POI."""
    corr = zarr.open(corr_filename, "r")

    raw_key = unhexlify(key)
    if len(raw_key) != 16:
        raise typer.BadParameter("The size of the round key is expected to be 16 bytes")

    last_step = corr.shape[1] - 1

    avg_ranks = []
    z_count = []
    for t in range(corr.shape[3]):
        t_ranks = []
        for j, k in enumerate(raw_key):
            sorted_guesses = []
            mat = np.array(corr[j, last_step, :, t])
            for _ in range(256):
                b = np.argmax(np.abs(mat))
                mat[b] = 0
                sorted_guesses.append(b)
            t_ranks.append(sorted_guesses.index(k))
        z_count.append(t_ranks.count(0))
        avg_ranks.append(np.mean(t_ranks))

    min_rank = np.min(avg_ranks)
    min_index = np.argmin(avg_ranks)

    best_z_count = np.max(z_count)
    best_z_index = np.argmax(z_count)

    print(f"{min_rank = }")
    print(f"{min_index = }")

    print(f"{best_z_count = }")
    print(f"{best_z_index = }")


@app.command()
def extract_correlations(
    corr_filename: Path,
    time_index: int,
    output_filename: Path,
    key: Annotated[
        Optional[str],
        typer.Option(help="The round key, if known, to highlight to correct trace"),
    ] = None,
) -> None:
    """Extract the correlation coefficients for all guesses."""
    corr = zarr.open(corr_filename, "r")

    if key is not None:
        raw_key = unhexlify(key)
        if len(raw_key) != 16:
            raise typer.BadParameter(
                "The size of the round key is expected to be 16 bytes"
            )
    else:
        raw_key = None

    chunk_size = 5000

    dataframes = []
    for key_index in range(16):
        for i in range(256):
            df = pd.DataFrame(
                {
                    "Measurement Index": np.arange(
                        0, corr.shape[1] * chunk_size, chunk_size
                    ),
                    "Correlation Value": corr[key_index, :, i, time_index],
                    "Name": f"Guess {i}",
                    "Byte": key_index,
                }
            )
            dataframes.append(df)

        if raw_key is not None:
            correct_key = raw_key[key_index]
            df = pd.DataFrame(
                {
                    "Measurement Index": np.arange(
                        0, corr.shape[1] * chunk_size, chunk_size
                    ),
                    "Correlation Value": corr[key_index, :, correct_key, time_index],
                    "Name": "Correct Guess",
                    "Byte": key_index,
                }
            )
            dataframes.append(df)

    result = pd.concat(dataframes)

    result.to_csv(output_filename)


@app.command()
def compare_spread(
    data1_filename: Path,
    data2_filename: Path,
    config_filename: Path,
    index: int,
    output_filename: Path,
    start_at: int = 10_000,
    stop_at: int = 20_000,
) -> None:
    """Compare the spread of two datasets at the given sampling point."""
    config = load_config(config_filename)

    if config["f_type"] is not None:
        filter_b, filter_a = signal.butter(
            config["f_order"],
            config["f_cutoff"],
            fs=12e6,
            btype=config["f_type"],
        )

    dataframes = []

    for filename in (data1_filename, data2_filename):
        data = zarr.open(filename, "r")
        samples_array = data["samples"]

        if config["f_type"] is not None:
            samples = signal.filtfilt(
                filter_b, filter_a, samples_array[start_at:stop_at], axis=2
            )
            samples = samples[:, :, index]
        else:
            samples = samples_array[start_at:stop_at, :, index]

        samples = samples.flatten()

        df = pd.DataFrame(
            {
                "Values": samples,
                "Name": filename,
            }
        )
        dataframes.append(df)

    result = pd.concat(dataframes)

    result.to_csv(output_filename)


@app.command()
def compose_correlations(
    corr_filenames: List[Path],
    output_filename: Path,
) -> None:
    """Compose (multiply) the correlation values from the provided files."""
    inputs = [zarr.open(f, "r") for f in corr_filenames]

    shape = list(inputs[0].shape)
    max_size = max([f.shape[1] for f in inputs])
    max_size_index = np.argmax([f.shape[1] for f in inputs])
    shape[1] = max_size

    result = zarr.open(
        output_filename,
        mode="w-",
        shape=shape,
        chunks=inputs[0].chunks,
        dtype="f",
    )

    for i in range(max_size):
        result[:, i, :, :] = inputs[max_size_index][:, i, :, :]
        for j, data in enumerate(inputs):
            if j == max_size_index:
                continue
            if i < data.shape[1]:
                result[:, i, :, :] *= data[:, i, :, :]
            else:
                result[:, i, :, :] *= data[:, -1, :, :]


if __name__ == "__main__":
    app()
