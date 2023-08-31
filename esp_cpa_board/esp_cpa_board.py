#!/usr/bin/env python3
"""EspCpaBoard main class."""

import array
import struct
import subprocess
import time
from enum import IntEnum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Optional

import fx2.format
import numpy as np
import usb1
from fx2 import FX2Device

from .gateware import configure_fpga

__all__ = ["EspCpaBoard"]


class CmdOpcode(IntEnum):
    """An enumeration class to represent command opcodes.

    Attributes:
        FPGA_CONFIG : opcode for FPGA configuration
        START_MEASUREMENT : opcode for starting power traces measurement
        STOP_MEASUREMENT : opcode for stopping power traces measurement
        SET_DAC : opcode for setting gain control DAC value
        SET_DUT_POWER : opcode for setting DUT power signal
        SET_DUT_CLK_EN : opcode for setting DUT clock enable signal
        SET_FLASH_PAYLOAD : opcode for setting the fake flash payload
        GET_TEMPERATURE : opcode for getting the DUT temperature
        SET_HEATER_PWM : opcode for setting the DUT heater PWM
    """

    FPGA_CONFIG = 0
    START_MEASUREMENT = 1
    STOP_MEASUREMENT = 2
    SET_DAC = 3
    SET_DUT_POWER = 4
    SET_DUT_CLK_EN = 5
    SET_FLASH_PAYLOAD = 6
    GET_TEMPERATURE = 7
    SET_HEATER_PWM = 8


class EspCpaBoardError(Exception):
    """Generic exception class for the EspCpaBoard."""

    pass


def sign_extend(value: int, bits: int) -> int:
    """Perform a 2-complement sign extend.

    Args:
        value (int): The value to extend
        bits (int): The position of the sign bit

    Returns:
        int: The extended, signed value
    """
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


class EspCpaBoard:
    """Main EspCpaBoard class."""

    def __init__(
        self, config: Dict[str, Any], firmware_path: Path = Path("./firmware")
    ) -> None:
        """Initialize the class.

        Args:
            config: A dictionary containing configuration parameters.
            firmware_path (path): Path to the firmware directory. Default is "./firmware".
        """
        self._firmware_path = firmware_path
        self._usb_ctx = usb1.USBContext()
        self._mutex = RLock()
        self._config = config

    @staticmethod
    def _lock(func: Callable) -> Callable:
        """Decorate a method to ensure its thread-safety."""

        def wrapper(self, *args, **kwargs):
            with self._mutex:
                r = func(self, *args, **kwargs)
            return r

        return wrapper

    def _get_fx2_firmware_data(self) -> list[tuple[int, bytes]]:
        """Compile and get the FX2 firmware data.

        Returns:
            list[tuple[int, bytes]]: The firmware data
        """
        if self._config["usb_acm_mode"]:
            usb_acm_mode = 1
        else:
            usb_acm_mode = 0
        subprocess.check_output(
            f"cd {self._firmware_path} && make clean && make USB_ACM_MODE={usb_acm_mode}",
            shell=True,
        )
        ihex_file = self._firmware_path / "firmware.ihex"
        ret = fx2.format.input_data(ihex_file.open("rb"), fmt="ihex")
        return ret

    def _build_payload(
        self,
        opcode: CmdOpcode,
        arg: int = 0,
        data: Optional[bytes] = None,
    ) -> bytes:
        """Build a command payload.

        Args:
            opcode (CmdOpcode): The command opcode
            arg (int, optional): The argument of the the command. Defaults to 0.
            data (Optional[bytes], optional): Additional payload. Defaults to None.

        Returns:
            bytes: The command payload
        """
        payload = struct.pack("<BI", opcode, arg)
        if data is not None:
            payload += data
        return payload

    def _send_command(
        self,
        opcode: CmdOpcode,
        arg: int = 0,
        data: Optional[bytes] = None,
        expect_ack: bool = True,
    ) -> None:
        """Send a command to the board.

        Args:
            opcode (CmdOpcode): The command opcode
            arg (int, optional): The argument of the the command. Defaults to 0.
            data (Optional[bytes], optional): Additional payload. Defaults to None.
            expect_ack (bool): Expect the command to be acked. Defaults to True.
        """
        payload = self._build_payload(opcode=opcode, arg=arg, data=data)

        self._ctrl_write(payload)

        if not expect_ack:
            return

        reply = self._ctrl_read(2)

        if reply != b"O\x00":
            raise EspCpaBoardError(f"Received invalid command reply: 0x{reply[0]:02x}")

    @_lock
    def configure(self) -> None:
        """Configure a board (firmware + gateware)."""
        firmware_data = self._get_fx2_firmware_data()
        device = FX2Device(vendor_id=0x04B4, product_id=0x8613)
        device.load_ram(firmware_data)
        time.sleep(1.5)  # Wait a bit to be sure device has been enumerated
        self.connect()
        configure_fpga(self._config, self._configure_fpga)

    def _ctrl_write(self, data: bytes, timeout: float = 0) -> None:
        """Write data to the USB vendor control endpoint.

        Args:
            data (bytes): The data to write
            timeout (float, optional): Timeout, expressed in seconds. Defaults to 0 (no timeout).
        """
        if timeout:
            timeout *= 1000  # ms

        for i in range(0, len(data), 64):  # Endpoint is limited to 64 bytes
            self._usb_handle.bulkWrite(1, data[i : i + 64], timeout=timeout)

    def _ctrl_read(self, size: int, timeout: float = 0) -> bytes:
        """Read data from the USB vendor control endpoint.

        Args:
            size (int): The size of the data to read
            timeout (float, optional): Timeout, expressed in seconds. Defaults to 0 (no timeout).

        Returns:
            bytes: The read data
        """
        if timeout:
            timeout *= 1000  # ms

        return bytes(
            self._usb_handle.bulkRead(usb1.ENDPOINT_IN | 1, size, timeout=timeout)
        )

    @_lock
    def connect(self) -> None:
        """Connect to the board control interface."""
        self._usb_handle = self._usb_ctx.openByVendorIDAndProductID(
            vendor_id=0x04B4, product_id=0x8613, skip_on_error=True
        )
        if self._usb_handle is None:
            raise EspCpaBoardError("Device not found")

    @_lock
    def set_dut_power(self, power: bool) -> None:
        """Set the DUT_POWER line level.

        Args:
            power (bool): The level
        """
        if power:
            arg = 1
        else:
            arg = 0
        self._send_command(CmdOpcode.SET_DUT_POWER, arg)

    @_lock
    def set_clk_en(self, en: bool) -> None:
        """Set the DUT_CLK_EN line level.

        Args:
            en (bool): The level
        """
        if en:
            arg = 1
        else:
            arg = 0
        self._send_command(CmdOpcode.SET_DUT_CLK_EN, arg)

    @_lock
    def set_amplifier_gain(self, gain: int) -> None:
        """Set the gain of the amplifier.

        Args:
            gain (int): The gain, expressed in percents.
        """
        target_voltage = gain * (1.1 - 0.1) / 100 + 0.1
        vref = 1.21  # V
        dac_gain = 1.5
        dac_count = round(target_voltage * 2**10 / (vref * dac_gain))
        self._send_command(CmdOpcode.SET_DAC, dac_count)

    def _adc_transfer_callback(self, transfer) -> None:
        """Callback function for USB transfer completion."""
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            return
        self._raw_adc_data += transfer.getBuffer()[: transfer.getActualLength()]

    @_lock
    def perform_measurement(
        self, n_samples: int = 0x8000, n_measurements: int = 1
    ) -> np.ndarray:
        """Perform a power trace measurement.

        Args:
            n_samples (int): Number of samples to be measured for each measurement. Default is 0x8000.
            n_measurements (int): Number of consecutive measurements to be performed. Default is 1.

        Returns:
            np.ndarray: Array containing the measurement results.
        """
        self._raw_adc_data = b""

        n_transfers = 1
        transfer_size = n_measurements * n_samples * 2

        # Prepare a large transfer queue to reach maximum bandwidth
        transfer_list = []
        for _ in range(n_transfers):
            transfer = self._usb_handle.getTransfer()
            transfer.setBulk(
                usb1.ENDPOINT_IN | 2,
                transfer_size,
                callback=self._adc_transfer_callback,
                timeout=30000,
            )
            transfer.submit()
            transfer_list.append(transfer)

        # Send the START_MEASUREMENT command
        start_adc_payload = self._build_payload(CmdOpcode.START_MEASUREMENT)

        cmd_transfer = self._usb_handle.getTransfer()
        cmd_transfer.setBulk(1, start_adc_payload)
        cmd_transfer.submit()

        transfer_list.append(cmd_transfer)

        # Wait for the end of the transfer
        while any(x.isSubmitted() for x in transfer_list):
            self._usb_ctx.handleEvents()

        # Stop the measurement in a clean way
        self._send_command(CmdOpcode.STOP_MEASUREMENT, expect_ack=False)

        # Parse data
        result = []
        for n in array.array("H", self._raw_adc_data):
            n10 = n & ((1 << 12) - 1)
            result.append(sign_extend(n10, 12))

        np_result = np.array(result)
        np_result = np_result.reshape(n_measurements, n_samples)

        return np_result

    def _configure_fpga(self, bitstream: bytes) -> None:
        """Configure the FPGA bitstream.

        Args:
            bitstream (bytes): The FPGA bitstream
        """
        self._send_command(CmdOpcode.FPGA_CONFIG, len(bitstream), bitstream)

    @_lock
    def set_flash_payload(self, payload: bytes) -> None:
        """Set the fake flash payload.

        Args:
            payload (bytes): The flash payload
        """
        self._send_command(CmdOpcode.SET_FLASH_PAYLOAD, data=payload)

    @_lock
    def get_temperature(self) -> float:
        """Get the DUT temperature read by the cartridge sensor.

        Returns:
            float: The temperature, expressed in °C
        """
        self._send_command(CmdOpcode.GET_TEMPERATURE, expect_ack=False)
        raw_temperature_code = self._ctrl_read(2)
        temperature_code = (raw_temperature_code[0] << 8) | raw_temperature_code[1]
        temperature = -45 + 175 * temperature_code / (2**16 - 1)
        return temperature

    @_lock
    def set_heater_pwm(self, value: int) -> None:
        """Set the cartridge heater PWM value.

        Args:
            value (int): The PWM value
        """
        self._send_command(CmdOpcode.SET_HEATER_PWM, value)
