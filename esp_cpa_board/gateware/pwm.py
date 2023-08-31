#!/usr/bin/env python3
"""PWM module implementation."""

from amaranth import Elaboratable, Module, Signal
from amaranth.lib.cdc import FFSynchronizer
from amaranth.sim import Simulator

__all__ = ["PWM"]


class PWM(Elaboratable):
    """PWM module."""

    def __init__(self):
        """Instantiate a PWM module."""
        self.o = Signal()
        self.value = Signal(8)

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        timer = Signal(8)
        m.d.sync += timer.eq(timer + 1)

        value = Signal(8)
        m.submodules += FFSynchronizer(self.value, value)

        with m.If(value == 0):
            m.d.comb += self.o.eq(0)
        with m.Elif(timer <= value):
            m.d.comb += self.o.eq(1)

        return m


if __name__ == "__main__":
    dut = PWM()

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    def proc():
        """Simulate a couple of clock cycles."""
        for v in range(256):
            yield dut.value.eq(v)
            for _ in range(255 * 10):
                yield

    sim.add_sync_process(proc)
    with sim.write_vcd("pwm.vcd", "pwm.gtkw", traces=[dut.o, dut.value]):
        sim.run()
