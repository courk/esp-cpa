#!/usr/bin/env python3
"""EspCpaBoard Platform definition."""

from typing import Callable, Optional

from amaranth.build import Attrs, Clock, Pins, Resource, Subsignal
from amaranth.vendor.lattice_ice40 import LatticeICE40Platform

__all__ = ["EspCpaBoardPlatform"]


def _I2CResource(*args, scl, sda, conn=None, attrs=None):  # noqa: N802
    """I2C resource helper."""
    io = []
    io.append(Subsignal("scl", Pins(scl, dir="io", conn=conn, assert_width=1)))
    io.append(Subsignal("sda", Pins(sda, dir="io", conn=conn, assert_width=1)))
    if attrs is not None:
        io.append(attrs)
    return Resource.family(*args, default_name="i2c", ios=io)


class EspCpaBoardPlatform(LatticeICE40Platform):
    """EspCpaBoard Platform definition."""

    device = "iCE5LP1K"
    package = "SG48"
    default_clk = "clk48"

    resources = [
        Resource(
            "clk48",
            0,
            Pins("20", dir="i"),
            Clock(48e6),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "led",
            0,
            Pins("11", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "adc_clk",
            0,
            Pins("44", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "adc_rdy",
            0,
            Pins("12", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "dut_boot",
            0,
            Pins("45", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "dut_en",
            0,
            Pins("42", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "dut_pwr",
            0,
            Pins("4", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "dut_clk",
            0,
            Pins("37", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "dut_spare",
            0,
            Pins("31", dir="i"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "fpga_int",
            0,
            Pins("25", dir="i"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "qspi_cs",
            0,
            Pins("39", dir="i"),
            Attrs(IO_STANDARD="SB_LVCMOS", PULLUP=1),
        ),
        Resource(
            "p_qspi_cs",
            0,
            Pins("36", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "qspi_clk",
            0,
            Pins("47", dir="i"),
            Attrs(IO_STANDARD="SB_LVCMOS", PULLUP=1),
        ),
        Resource(
            "qspi_sd0",
            0,
            Pins("41", dir="io"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "qspi_sd1",
            0,
            Pins("38", dir="io"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        Resource(
            "heat_ctrl",
            0,
            Pins("31", dir="o"),
            Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
        _I2CResource(
            "i2c",
            0,
            scl="3",
            sda="48",
            attrs=Attrs(IO_STANDARD="SB_LVCMOS"),
        ),
    ]

    connectors: list[Resource] = []

    def __init__(  # noqa: D107
        self, *, toolchain="IceStorm", configure_function: Optional[Callable] = None
    ):
        super().__init__(toolchain=toolchain)
        self._configure_function = configure_function

    def toolchain_program(self, products, name):
        with products.extract("{}.bin".format(name)) as bitstream_filename:
            bitstream = open(bitstream_filename, "rb").read()
            self._configure_function(bitstream)
