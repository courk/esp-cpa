#!/usr/bin/env python3
"""I2cControl module implementation."""

from enum import IntEnum

from amaranth import DomainRenamer, Elaboratable, Module, Signal
from amaranth.lib.cdc import PulseSynchronizer

from .i2c import I2CTarget


class CmdOpcode(IntEnum):
    """Supported command opcodes of the I2C control interface."""

    SET_IO_LEVELS = 0
    SET_FLASH_PAYLOAD = 1
    START_MEASUREMENT = 2
    SET_HEAT_CTRL_PWM = 3


class I2cControl(Elaboratable):
    """I2cControl module."""

    def __init__(self):
        """Instantiate a I2CControl module."""
        self.dut_boot = Signal()
        self.dut_en = Signal()
        self.dut_pwr = Signal()
        self.dut_clk_en = Signal()

        self.flash_payload = Signal(128)
        self.start_measurement = Signal()
        self.heat_ctrl_pwm = Signal(8)

    def elaborate(self, platform):
        m = Module()

        i2c_pads = platform.request("i2c", 0)

        i2c_target = DomainRenamer("slow")(I2CTarget(i2c_pads))
        m.submodules += i2c_target

        ps = PulseSynchronizer("slow", "sync")
        i2c_write_ready = Signal()
        m.d.comb += [ps.i.eq(i2c_target.write), i2c_write_ready.eq(ps.o)]
        m.submodules += ps

        m.d.comb += i2c_target.address.eq(0x42)

        io_levels = Signal(8)

        payload_offset = Signal(range(0, 16))

        with m.FSM():
            with m.State("READ_OPCODE"):
                with m.If(i2c_write_ready):
                    m.d.sync += payload_offset.eq(0)
                    with m.Switch(i2c_target.data_i):
                        with m.Case(CmdOpcode.SET_IO_LEVELS):
                            m.next = "READ_IO_LEVELS"
                        with m.Case(CmdOpcode.SET_FLASH_PAYLOAD):
                            m.next = "READ_FLASH_PAYLOAD"
                        with m.Case(CmdOpcode.START_MEASUREMENT):
                            m.d.comb += self.start_measurement.eq(1)
                        with m.Case(CmdOpcode.SET_HEAT_CTRL_PWM):
                            m.next = "READ_HEAT_CTRL_PWM"

            with m.State("READ_IO_LEVELS"):
                with m.If(i2c_write_ready):
                    m.d.sync += io_levels.eq(i2c_target.data_i)
                    m.next = "READ_OPCODE"

            with m.State("READ_FLASH_PAYLOAD"):
                with m.If(i2c_write_ready):
                    m.d.sync += [
                        self.flash_payload.bit_select(payload_offset << 3, 8).eq(
                            i2c_target.data_i[::-1]  # SPI data will be sent LSB first
                        ),
                        payload_offset.eq(payload_offset + 1),
                    ]
                    with m.If(payload_offset == 15):
                        m.next = "READ_OPCODE"

            with m.State("READ_HEAT_CTRL_PWM"):
                with m.If(i2c_write_ready):
                    m.d.sync += self.heat_ctrl_pwm.eq(i2c_target.data_i)
                    m.next = "READ_OPCODE"

        # ACK all writes
        with m.If(i2c_target.write):
            m.d.comb += i2c_target.ack_o.eq(1)

        # Split io_levels into relevant signals
        m.d.comb += [
            self.dut_boot.eq(io_levels[0]),
            self.dut_en.eq(io_levels[1]),
            self.dut_pwr.eq(io_levels[2]),
            self.dut_clk_en.eq(io_levels[3]),
        ]

        return m
