#!/usr/bin/env python3
"""Top module implementation."""

from pathlib import Path
from typing import Any, Callable, Dict

import typer
from amaranth import (
    ClockDomain,
    Const,
    DomainRenamer,
    Elaboratable,
    Instance,
    Module,
    Signal,
)

from ..utils import load_config
from .adc import Adc
from .esp_cpa_board_platform import EspCpaBoardPlatform
from .fake_spi_flash import FakeSpiFlash
from .gearbox import GearBox
from .i2c_control import I2cControl
from .measurement_engine import MeasurementEngine
from .pwm import PWM


class Top(Elaboratable):
    """Top module."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Instantiate gateware top module.

        Args:
            config (Dict[str, Any]): The board configuration data
        """
        super().__init__()
        self._config = config

    def elaborate(self, platform):
        m = Module()

        # Use HSOC at 6MHz to generate a slow clock domain
        clk_slow = Signal()

        hfosc = Instance(
            "SB_HFOSC",
            p_CLKHF_DIV="0b11",  # div8
            i_CLKHFEN=Const(1),
            i_CLKHFPU=Const(1),
            o_CLKHF=clk_slow,
        )
        m.submodules += hfosc

        cd_slow = ClockDomain(reset_less=True)
        m.domains += cd_slow
        m.d.comb += cd_slow.clk.eq(clk_slow)

        adc_clk = platform.request("adc_clk", 0)
        adc_rdy = platform.request("adc_rdy", 0)

        dut_boot = platform.request("dut_boot", 0)
        dut_en = platform.request("dut_en", 0)
        dut_pwr = platform.request("dut_pwr", 0)

        dut_clk = platform.request("dut_clk", 0)

        qspi_cs = platform.request("qspi_cs", 0)
        p_qspi_cs = platform.request("p_qspi_cs", 0)
        qspi_clk = platform.request("qspi_clk", 0)
        qspi_in = platform.request("qspi_sd1", 0)

        heat_ctrl = platform.request("heat_ctrl", 0)

        i2c_control = I2cControl()
        gearbox = GearBox(self._config["clk40"])
        heat_ctrl_pwm = DomainRenamer("slow")(PWM())

        m.submodules += i2c_control
        m.submodules += gearbox
        m.submodules += heat_ctrl_pwm

        if self._config["target_name"] != "esp_idf":
            adc = Adc(self._config["n_samples"])
            fake_spi_flash = FakeSpiFlash(
                self._config["target_name"], self._config["block_target"]
            )
            measurement_engine = MeasurementEngine(self._config["averaging"])

            m.submodules += adc
            m.submodules += fake_spi_flash
            m.submodules += measurement_engine

        measurement_ongoing = Signal()
        measurement_dut_en = Signal()

        if self._config["target_name"] != "esp_idf":
            m.d.comb += [
                # ADC
                adc_clk.eq(adc.adc_clk),
                adc_rdy.eq(adc.adc_rdy),
                # fake_spi_flash
                fake_spi_flash.payload.eq(i2c_control.flash_payload),
                fake_spi_flash.en.eq(measurement_engine.fake_spi_flash_en),
                fake_spi_flash.spi_clk.eq(qspi_clk),
                qspi_in.o.eq(fake_spi_flash.spi_out),
                qspi_in.oe.eq(fake_spi_flash.spi_out_en),
                # Measurement engine
                measurement_engine.start.eq(i2c_control.start_measurement),
                measurement_ongoing.eq(measurement_engine.busy),
                adc.trigger.eq(measurement_engine.adc_trigger),
                measurement_engine.adc_done.eq(adc.done),
                measurement_dut_en.eq(measurement_engine.dut_en),
                measurement_engine.flash_payload_sent.eq(fake_spi_flash.payload_sent),
                measurement_engine.flash_payload_almost_sent.eq(
                    fake_spi_flash.payload_almost_sent
                ),
                # Gearbox
                gearbox.medium_en.eq(measurement_engine.medium_clk_speed_req),
            ]

        m.d.comb += [
            # IOs
            dut_pwr.eq(i2c_control.dut_pwr),
            dut_clk.eq(gearbox.clk_out),
            # Heat control
            heat_ctrl.eq(heat_ctrl_pwm.o),
            heat_ctrl_pwm.value.eq(i2c_control.heat_ctrl_pwm),
        ]

        # Handle sharing of the DUT_EN and DUT_BOOT lines
        with m.If(measurement_ongoing):
            m.d.comb += [
                dut_en.eq(measurement_dut_en),
                gearbox.en.eq(measurement_dut_en),
                dut_boot.eq(1),
                p_qspi_cs.eq(1),  # Physical flash will not respond
            ]
        with m.Else():
            m.d.comb += [
                dut_en.eq(i2c_control.dut_en),
                gearbox.en.eq(i2c_control.dut_clk_en),
                dut_boot.eq(i2c_control.dut_boot),
                p_qspi_cs.eq(qspi_cs),  # Physical flash will respond
            ]

        # Turn the LED off when a measurement is on-going
        led = platform.request("led", 0)
        m.d.comb += led.eq(measurement_ongoing)

        return m


def configure_fpga(config: Dict[str, Any], configure_function: Callable):
    """Build and program the target FPGA."""
    platform = EspCpaBoardPlatform(configure_function=configure_function)
    platform.build(Top(config), do_program=True)


def _build_gateware(
    measurement_config: Path,
):
    config = load_config(measurement_config)
    platform = EspCpaBoardPlatform()
    platform.build(Top(config))


def build_gateware():
    """Build the gateware bitstream."""
    typer.run(_build_gateware)
