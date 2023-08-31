#!/usr/bin/env python3
"""Plot analysis results."""

from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import typer
from plotly.subplots import make_subplots

app = typer.Typer()


def _render(ctx: typer.Context, fig: go.Figure):
    """Render the given figure to HTML."""
    fig.update_layout(template="plotly_white")

    fig.update_xaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
    )
    fig.update_yaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
    )

    if ctx.obj.json_output:
        fig.write_json(
            ctx.obj.output_filename,
        )
    else:
        fig.write_html(ctx.obj.output_filename, auto_open=True)


@app.command()
def plot_ranks(ctx: typer.Context, input_file: Path):
    """Plot the rank evolution of each byte."""
    df = pd.read_csv(input_file)

    fig = px.line(
        df,
        x="Measurement Index",
        y="Rank",
        color="Name",
        title=ctx.obj.graph_title,
        render_mode="svg",
    )
    fig.update_traces(
        line=dict(dash="dash", width=5, color="red"), selector=dict(name="Average")
    )

    _render(ctx, fig)


@app.command()
def plot_traces(ctx: typer.Context, input_file: Path):
    """Plot the rank evolution of each byte."""
    df = pd.read_csv(input_file)

    fig = px.line(
        df,
        x="Sample Index",
        y="Value",
        color="Name",
        title=ctx.obj.graph_title,
    )

    _render(ctx, fig)


@app.command()
def plot_spread(ctx: typer.Context, input_file: Path, pruning_rate: float = 0.9):
    """Plot the spread at a given timestamp."""
    df = pd.read_csv(input_file)

    n_rows = len(df[df["Name"] == "Raw"]["Value"])
    mask = np.random.rand(n_rows) > pruning_rate

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            name="Samples",
            x=df[df["Name"] == "Raw"]["Measurement Index"][mask],
            y=df[df["Name"] == "Raw"]["Value"][mask],
            mode="markers",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            name="Temperature",
            x=df[df["Name"] == "Temperature"]["Measurement Index"][mask],
            y=df[df["Name"] == "Temperature"]["Temperature"][mask],
        ),
        secondary_y=True,
    )

    fig.update_layout(title_text=ctx.obj.graph_title)
    fig.update_xaxes(title_text="Measurement Index")
    fig.update_yaxes(title_text="Sample Value (LSB)", secondary_y=False)
    fig.update_yaxes(title_text="Temperature (°C)", secondary_y=True)

    _render(ctx, fig)


@app.command()
def plot_correlations(ctx: typer.Context, input_file: Path, step_size: int = 50_000):
    """Plot the correlation coefficients evolution of each guess."""
    df = pd.read_csv(input_file)

    fig = px.line(
        df[df["Measurement Index"] % step_size == 0],
        x="Measurement Index",
        y="Correlation Value",
        color="Name",
        facet_col="Byte",
        facet_col_wrap=4,
        title=ctx.obj.graph_title,
        height=800,
    )
    fig.update_traces(line=dict(color="grey"))
    fig.update_traces(line=dict(color="red"), selector=dict(name="Correct Guess"))

    _render(ctx, fig)


@app.command()
def plot_correlations_at_index(
    ctx: typer.Context, input_file: Path, byte_index: List[int], step_size: int = 10_000
):
    """Plot the correlation coefficients evolution of each guess."""
    df = pd.read_csv(input_file)

    df = df[df["Measurement Index"] % step_size == 0]

    if len(byte_index) == 1:
        fig = px.line(
            df[df["Byte"] == byte_index[0]],
            x="Measurement Index",
            y="Correlation Value",
            color="Name",
            title=ctx.obj.graph_title,
        )
    else:
        fig = px.line(
            df[df["Byte"].isin(byte_index)],
            x="Measurement Index",
            y="Correlation Value",
            color="Name",
            facet_col="Byte",
            title=ctx.obj.graph_title,
        )
    fig.update_traces(line=dict(color="grey"))
    fig.update_traces(line=dict(color="red"), selector=dict(name="Correct Guess"))

    _render(ctx, fig)


@app.command()
def plot_compare_spread(
    ctx: typer.Context, input_file: Path, separator: Optional[int] = None
):
    """Plot a sample spread comparison."""
    df = pd.read_csv(input_file)

    vmin = np.min(df["Values"])
    vmax = np.max(df["Values"])

    dataframes = []
    for name in df["Name"].unique():
        counts, bins = np.histogram(
            df["Values"][df["Name"] == name], bins=512, range=(vmin, vmax)
        )
        dataframes.append(
            pd.DataFrame(
                {
                    "Counts": counts,
                    "Values": bins[:-1],
                    "Name": name,
                }
            )
        )

    processed_df = pd.concat(dataframes)

    fig = px.bar(
        processed_df,
        x="Values",
        y="Counts",
        color="Name",
        title=ctx.obj.graph_title,
        barmode="overlay",
    )

    fig.update_traces({"marker_line_width": 0})
    fig.update_layout({"bargap": 0})

    if separator is not None:
        fig.add_vline(x=separator)

    _render(ctx, fig)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = False,
    output_filename: Path = Path("/tmp/render.html"),
    graph_title: Optional[str] = None,
):
    """Plotting tools for analysis results."""
    ctx.obj = SimpleNamespace(
        json_output=json_output,
        output_filename=output_filename,
        graph_title=graph_title,
    )


if __name__ == "__main__":
    app()
