#!/usr/bin/env python3
"""Fake SPI Flash module implementation."""

from typing import Any, List

from amaranth import Cat, Const, Elaboratable, Module, Signal
from amaranth.lib.cdc import FFSynchronizer
from amaranth.sim import Simulator


class FakeSpiFlash(Elaboratable):
    """Fake SPI flash module."""

    def __init__(self, target_name: str, block_target: List[int]):
        """Instantiate an FakeSpiFlash module.

        Args:
            target_name (str): The name of the target chip ("esp32", "esp32c3", or "esp32c6")
            block_target (List[int]): The 16-byte block index to target
        """
        # Physical SPI interface
        self.spi_clk = Signal()
        self.spi_out = Signal()
        self.spi_out_en = Signal()

        # Control
        self.en = Signal()
        self.payload_sent = Signal()
        self.payload_almost_sent = Signal()
        self.payload = Signal(128)

        self._target_name = target_name
        self._block_target = block_target

    def _gen_bitsream_chunks(self) -> List[Any]:
        """Generate the bitstream to be sent by the fake SPI flash."""
        bitstream_chunks = []

        bitstream_chunks.append(Const(0, 1))  # Dummy

        if self._target_name == "esp32c3":
            bitstream_chunks.append(Const(0x00, 8))  # Dummy
        elif self._target_name == "esp32c6":
            bitstream_chunks.append(Const(0x00, 8))  # Dummy (0xAB cmd)
            bitstream_chunks.append(Const(0x00, 8))  # Dummy (0x04 cmd)
        elif self._target_name == "esp32":
            for _ in range(4):
                bitstream_chunks.append(Const(0xFF, 8))  # Dummy
            bitstream_chunks.append(
                Const(0x15, 8)[::-1]
            )  # Electronic signature response
        else:
            raise NotImplementedError(f"unknown target: {self._target_name}")

        for _ in range(4):
            bitstream_chunks.append(Const(0xFF, 8))  # Dummy (0x03 cmd + 3 dummy)

        for block_index in (0, 1):
            if block_index not in self._block_target:
                if block_index == 0:
                    for _ in range(16):
                        bitstream_chunks.append(Const(0x00, 8))  # Flash content (dummy)
            else:
                bitstream_chunks.append(self.payload)  # Flash content

        bitstream_chunks.append(Const(1, 1))  # Constantly output 0xFF after the payload

        return bitstream_chunks

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        bitstream_chunks = self._gen_bitsream_chunks()
        bitstream_size = sum(len(s) for s in bitstream_chunks)
        bitstream = Signal(bitstream_size)
        m.d.comb += bitstream.eq(Cat(*bitstream_chunks))

        spi_clk = Signal()
        m.submodules += FFSynchronizer(self.spi_clk, spi_clk)

        # Falling edge clock detection
        falling_edge = Signal()
        previous_spi_clk = Signal()
        m.d.sync += previous_spi_clk.eq(spi_clk)
        with m.If(~spi_clk & previous_spi_clk):
            m.d.comb += falling_edge.eq(1)

        # Connect spi_out
        bitstream_offset = Signal(range(0, len(bitstream)))
        b = Signal()
        m.d.comb += b.eq(bitstream.bit_select(bitstream_offset, 1))
        m.d.comb += [self.spi_out.eq(b), self.spi_out_en.eq(self.en)]
        with m.If(self.en):
            with m.If(falling_edge & (bitstream_offset != len(bitstream) - 1)):
                m.d.sync += bitstream_offset.eq(bitstream_offset + 1)
        with m.Else():
            m.d.sync += bitstream_offset.eq(0)

        # Trigger management, sent just after the payload has been transmitted
        payload_send_level = Signal()
        previous_payload_send_level = Signal()
        with m.If(bitstream_offset == bitstream_size - 2):
            m.d.comb += payload_send_level.eq(1)

        m.d.sync += previous_payload_send_level.eq(payload_send_level)

        with m.If(payload_send_level & ~previous_payload_send_level):
            m.d.comb += self.payload_sent.eq(1)

        # Trigger management, sent just before the payload has been entirely transmitted
        payload_almost_send_level = Signal()
        previous_payload_almost_send_level = Signal()
        with m.If(bitstream_offset == bitstream_size - 4):
            m.d.comb += payload_almost_send_level.eq(1)

        m.d.sync += previous_payload_almost_send_level.eq(payload_almost_send_level)

        with m.If(payload_almost_send_level & ~previous_payload_almost_send_level):
            m.d.comb += self.payload_almost_sent.eq(1)

        return m


if __name__ == "__main__":
    dut = FakeSpiFlash(target_name="esp32", block_target=[0, 1])

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    def gen_spi_clk():
        """Generate one SPI clock cycle."""
        for _ in range(4):
            yield
        yield dut.spi_clk.eq(1)
        for _ in range(4):
            yield
        yield dut.spi_clk.eq(0)

    def proc():
        """Simulate the first transactions observed with the ESP32."""
        payload = 0
        for i in range(16):
            payload |= i << i * 8

        yield dut.payload.eq(payload)

        yield dut.en.eq(1)

        for _ in range(50):
            yield

        # Electronic signature
        for _ in range(5 * 8):
            yield from gen_spi_clk()

        for _ in range(50):
            yield

        # Payload
        for _ in range(600):
            yield from gen_spi_clk()

    sim.add_sync_process(proc)
    with sim.write_vcd(
        "fake_spi_flash.vcd",
        "fake_spi_flash.gtkw",
        traces=[dut.spi_clk, dut.spi_out, dut.payload_sent, dut.payload_almost_sent],
    ):
        sim.run()
