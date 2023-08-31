#!/usr/bin/env python3
"""ADC module implementation."""

from amaranth import Elaboratable, Module, Signal
from amaranth.sim import Simulator

__all__ = ["Adc"]


class Adc(Elaboratable):
    """ADC module."""

    def __init__(self, n_samples: int, sps: float = 12e6, f_sys: float = 48e6):
        """Instantiate an ADC module.

        Args:
            n_samples (int): The number of samples to measure.
            sps (float, optional): The target SPS of the ADC. Defaults to 10e6 Hz.
            f_sys (float, optional): The system clock frequency. Defaults to 48e6 Hz.
        """
        # Physical interface outputs
        self.adc_clk = Signal()
        self.adc_rdy = Signal()

        # Outputs
        self.trigger = Signal()
        self.done = Signal()

        # Input
        self._n_samples = n_samples

        self._timer_max = int(f_sys / sps / 2 - 1)

    def elaborate(self, platform):  # noqa: D102
        timer = Signal(range(0, self._timer_max + 1))

        m = Module()

        adc_rdy = Signal()
        sample_counter = Signal(range(self._n_samples + 1))

        with m.FSM():
            with m.State("WAIT_TRIGGER"):
                with m.If(self.trigger):
                    m.d.sync += sample_counter.eq(0)
                    m.next = "SAMPLE"

            with m.State("SAMPLE"):
                m.d.comb += self.adc_rdy.eq(adc_rdy)
                with m.If(adc_rdy):
                    m.d.sync += sample_counter.eq(sample_counter + 1)
                with m.If(sample_counter & self._n_samples):
                    m.d.comb += self.done.eq(1)
                    m.next = "WAIT_TRIGGER"

        # ADC clock and internal adc_rdy generation
        with m.If(timer != self._timer_max):
            m.d.sync += timer.eq(timer + 1)
        with m.Else():
            m.d.sync += timer.eq(0)
            m.d.sync += self.adc_clk.eq(~self.adc_clk)
            with m.If(self.adc_clk):
                m.d.comb += adc_rdy.eq(1)

        return m


if __name__ == "__main__":
    dut = Adc(256)

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    def proc():
        """Simulate a couple of clock cycles."""
        for _ in range(20):
            yield

        yield dut.trigger.eq(1)
        yield
        yield dut.trigger.eq(0)

        counter = 0
        while True:
            ready = yield dut.adc_rdy
            done = yield dut.done
            if ready:
                counter += 1
            if done:
                break
            yield

        assert counter == 256, f"Mismatch is sample count 256 != {counter}"

        for _ in range(200):
            yield

    sim.add_sync_process(proc)
    with sim.write_vcd(
        "adc.vcd", "adc.gtkw", traces=[dut.adc_clk, dut.adc_rdy, dut.trigger, dut.done]
    ):
        sim.run()
