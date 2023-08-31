#!/usr/bin/env python3
"""MeasurementEngine module implementation."""

import math

from amaranth import Elaboratable, Module, Signal
from amaranth.sim import Simulator


class MeasurementEngine(Elaboratable):
    """MeasurementEngine module."""

    def __init__(self, n_cycles: int, f_sys: float = 48e6):
        """Instantiate a MeasurementEngine module."""
        # Input
        self.start = Signal()

        # Output
        self.busy = Signal()

        # Output
        self.adc_trigger = Signal()
        # Input
        self.adc_done = Signal()

        # Output
        self.fake_spi_flash_en = Signal()

        # Output
        self.dut_en = Signal()

        # Input
        self.flash_payload_almost_sent = Signal()
        self.flash_payload_sent = Signal()

        # Output
        self.medium_clk_speed_req = Signal()

        self._n_cycles = n_cycles
        self._f_sys = f_sys

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        # At least 50µs is needed to reset the system
        counter_max = int(50e-6 * self._f_sys)
        counter_n_bits = int(math.log2(counter_max)) + 1
        reset_delay_counter = Signal(counter_n_bits + 1)

        measurement_cycle_counter = Signal(range(self._n_cycles + 1))

        with m.FSM() as fsm:
            with m.State("WAIT_START"):
                with m.If(self.start):
                    m.d.sync += measurement_cycle_counter.eq(0)
                    m.next = "DUT_RESET_DELAY"

            with m.State("DUT_RESET_DELAY"):
                with m.If(reset_delay_counter & (1 << counter_n_bits)):
                    m.next = "WAIT_SPI"
                with m.Else():
                    m.d.sync += reset_delay_counter.eq(reset_delay_counter + 1)

            with m.State("WAIT_SPI"):
                with m.If(self.flash_payload_almost_sent):
                    m.next = "WAIT_ADC_DONE"

            with m.State("WAIT_ADC_DONE"):
                with m.If(self.adc_done):
                    m.d.sync += measurement_cycle_counter.eq(
                        measurement_cycle_counter + 1
                    )
                    m.next = "LOOP"

            with m.State("LOOP"):
                with m.If(measurement_cycle_counter == self._n_cycles):
                    m.next = "WAIT_START"
                with m.Else():
                    m.d.sync += reset_delay_counter.eq(0)
                    m.next = "DUT_RESET_DELAY"

            m.d.comb += self.busy.eq(~fsm.ongoing("WAIT_START"))

            m.d.comb += self.medium_clk_speed_req.eq(
                fsm.ongoing("WAIT_SPI")
            )  # Run DUT faster when waiting for SPI transaction trigger

            m.d.comb += self.fake_spi_flash_en.eq(
                fsm.ongoing("WAIT_ADC_DONE") | fsm.ongoing("WAIT_SPI")
            )

            m.d.comb += self.dut_en.eq(
                fsm.ongoing("WAIT_ADC_DONE") | fsm.ongoing("WAIT_SPI")
            )

        # Start the ADC as soon as the payload has been transmitted
        m.d.comb += self.adc_trigger.eq(self.flash_payload_sent)

        return m


if __name__ == "__main__":
    dut = MeasurementEngine(n_cycles=8)

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    def proc():
        """Simulate the usage of the MeasurementEngine."""
        for _ in range(500):
            yield

        yield dut.n_cycles.eq(3)  # (1 << 3) = 8 cycles
        yield dut.start.eq(1)
        yield
        yield dut.start.eq(0)

        for _ in range(8):
            for _ in range(6000):
                yield

            yield dut.flash_payload_almost_sent.eq(1)
            yield
            yield dut.flash_payload_almost_sent.eq(0)

            for _ in range(500):
                yield

            yield dut.flash_payload_sent.eq(1)
            yield
            yield dut.flash_payload_sent.eq(0)

            for _ in range(500):
                yield

            yield dut.adc_done.eq(1)
            yield
            yield dut.adc_done.eq(0)

        for _ in range(500):
            yield

    sim.add_sync_process(proc)
    with sim.write_vcd(
        "measurement_engine.vcd",
        "measurement_engine.gtkw",
        traces=[
            dut.start,
            dut.busy,
            dut.adc_trigger,
            dut.adc_done,
            dut.dut_en,
            dut.flash_payload_sent,
            dut.flash_payload_almost_sent,
            dut.fake_spi_flash_en,
            dut.medium_clk_speed_req,
        ],
    ):
        sim.run()
