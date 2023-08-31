#!/usr/bin/env python3
"""Gearbox module implementation."""

from amaranth import ClockSignal, Const, Elaboratable, Instance, Module, Signal
from amaranth.sim import Simulator


class ClockDivider(Elaboratable):
    """ClockDivider module."""

    def __init__(self, div: int):
        """Instantiate a ClockDivider module.

        Args:
            div (int): The clock divider ratio to use
        """
        self._div = div
        self.output = Signal()

    def elaborate(self, platform):
        m = Module()

        max = int(self._div / 2 - 1)
        counter = Signal(range(0, max + 1))

        with m.If(counter == max):
            m.d.sync += self.output.eq(~self.output)
            m.d.sync += counter.eq(0)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m


class GearBox(Elaboratable):
    """Gearbox module."""

    def __init__(
        self,
        fast_output: bool = False,
        slow_f: float = 500e3,
        medium_f: float = 8e6,
        f_sys: float = 48e6,
    ):
        """Instantiate a GearBox module.

        Args:
            fast_output (bool, optional): Output a 40 MHz clock signal (nominal frequency for Espressif's components).
            slow_f (float, optional): The slow frequency. Defaults to 500e3 Hz.
            medium_f (float, optional): The medium frequency. Defaults to 6e6 Hz.
            f_sys (float, optional): The system clock frequency. Defaults to 48e6 Hz.
        """
        self.en = Signal()
        self.medium_en = Signal()
        self.clk_out = Signal()

        self._fast_output = fast_output
        self._f_sys = f_sys
        self._slow_f = slow_f
        self._medium_f = medium_f

    def elaborate(self, platform):
        m = Module()

        if not self._fast_output:
            div_slow = self._f_sys / self._slow_f
            max_slow = int(div_slow / 2 - 1)

            div_medium = self._f_sys / self._medium_f
            max_medium = int(div_medium / 2 - 1)

            counter = Signal(range(0, max_slow + 1))
            target = Signal(range(0, max_slow + 1))

            with m.If(counter == target):
                m.d.sync += self.clk_out.eq(~self.clk_out & self.en)
                m.d.sync += counter.eq(0)
                with m.If(self.medium_en):
                    m.d.sync += target.eq(max_medium)
                with m.Else():
                    m.d.sync += target.eq(max_slow)
            with m.Else():
                m.d.sync += counter.eq(counter + 1)
        else:
            clk40 = Signal()

            pll = Instance(
                "SB_PLL40_CORE",
                p_FEEDBACK_PATH="SIMPLE",
                p_DIVR=2,
                p_DIVF=39,
                p_DIVQ=4,
                p_FILTER_RANGE=1,
                o_LOCK=Signal(),
                i_RESETB=Const(1),
                i_BYPASS=Const(0),
                i_REFERENCECLK=ClockSignal(),
                o_PLLOUTCORE=clk40,
            )
            m.submodules += pll

            with m.If(self.en):
                m.d.comb += self.clk_out.eq(clk40)

        return m


if __name__ == "__main__":
    dut = GearBox()

    def proc():
        """Simulator."""
        for _ in range(1000):
            yield

        yield dut.medium_en.eq(1)

        for _ in range(1000):
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    sim.add_sync_process(proc)

    with sim.write_vcd(
        "gearbox.vcd",
        "gearbox.gtkw",
        traces=[dut.clk_out],
    ):
        sim.run()
