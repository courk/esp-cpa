#!/usr/bin/env python3
"""Control and configuration tools for the ESP CPA Board."""

from pathlib import Path
from types import SimpleNamespace

import typer
from typing_extensions import Annotated

from esp_cpa_board import EspCpaBoard, load_config

app = typer.Typer()


@app.command()
def configure_board(ctx: typer.Context) -> None:
    """Configure the board, with both firmware and gateware."""
    config = load_config(ctx.obj.measurement_config)
    board = EspCpaBoard(config)
    board.configure()


@app.command()
def set_dut_power(ctx: typer.Context, power: bool) -> None:
    """Control the DUT power supply."""
    board = EspCpaBoard(ctx.obj.measurement_config)
    board.connect()
    board.set_dut_power(power)


@app.command()
def enable_dut_clock(ctx: typer.Context) -> None:
    """Enable the DUT clock."""
    board = EspCpaBoard(ctx.obj.measurement_config)
    board.connect()
    board.set_clk_en(True)


@app.command()
def disable_dut_clock(ctx: typer.Context) -> None:
    """Disable the DUT clock."""
    board = EspCpaBoard(ctx.obj.measurement_config)
    board.connect()
    board.set_clk_en(False)


@app.command()
def get_temperature(ctx: typer.Context) -> None:
    """Get the temperature read by the cartridge sensor."""
    board = EspCpaBoard(ctx.obj.measurement_config)
    board.connect()
    temperature = board.get_temperature()
    print(f"{temperature = :.2f} °C")


@app.command()
def set_heater_pwm(
    ctx: typer.Context,
    value: Annotated[
        int,
        typer.Argument(
            min=0,
            max=255,
            help="The PWM value",
        ),
    ],
) -> None:
    """Set the cardtrige heater PWM value."""
    board = EspCpaBoard(ctx.obj.measurement_config)
    board.connect()
    board.set_heater_pwm(value)


@app.callback()
def main(
    ctx: typer.Context,
    measurement_config: Path,
):
    """Control and configuration tools for the ESP CPA Board."""
    ctx.obj = SimpleNamespace(measurement_config=measurement_config)


if __name__ == "__main__":
    app()
