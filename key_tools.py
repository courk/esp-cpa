#!/usr/bin/env python3
"""Various AES-related tools."""

import struct
from binascii import unhexlify
from pathlib import Path
from typing import List, Tuple

import typer
from aeskeyschedule import key_schedule, reverse_key_schedule
from Crypto.Cipher import AES
from rich import print
from rich.table import Table

from esp_cpa_board.aes_utils import (
    calculate_next_xts_tweak,
    calculate_previous_xts_tweak,
    mix_columns,
    mix_columns_inv,
    xor,
)

app = typer.Typer()


def _xts_key_recovery(
    tk0: bytes,
    mk1: bytes,
) -> Tuple[bytes, List[bytes]]:
    """Recover encryption keys and tweak values.

    Args:
        tk0 (bytes): The tweaked key of the first decryption round
        mk1 (bytes): The modified key of the second decryption round

    weturns:
        Tuple[bytes, List[bytes]]: The encryption key and tweaks
    """
    k1 = mix_columns(mk1)  # Second decryption round key

    key_e = reverse_key_schedule(k1, 9)  # Recover decryption key

    k0 = key_schedule(key_e)[-1]  # Compute first decyption round key

    t6 = xor(k0, tk0)  # Recover tweak at tweak index 6

    # Recover all other tweaks
    tn = [b""] * 8
    tn[6] = t6
    tn[7] = calculate_next_xts_tweak(t6)
    for i in range(6):
        tn[6 - i - 1] = calculate_previous_xts_tweak(tn[6 - i])

    return (key_e, tn)


def _xts_encrypt_decrypt(
    data_input_filename: Path,
    tk0: bytes,
    mk1: bytes,
    data_output_filename: Path,
    do_decrypt: bool,
):
    """Decrypt/Encrypt the first (flash offset = 0) 128 bits of AEX-XTS encrypted data.

    Args:
        data_input_filename (Path): Input data file
        tk0 (bytes): The tweaked key of the first decryption round
        mk1 (bytes): The modified key of the second decryption round
        data_output_filename (Path): Output data file
        do_decrypt (bool): Set to True to perform decryption, False for encryption
    """
    key_e, tn = _xts_key_recovery(tk0, mk1)

    cipher_e = AES.new(key_e, AES.MODE_ECB)

    encrypted_data = open(data_input_filename, "rb").read()
    assert len(encrypted_data) == 0x80, "Invalid data size"

    encrypted_data = encrypted_data[::-1]

    decrypted_data = b""
    for i in range(8):
        block = encrypted_data[i * 16 : (i + 1) * 16]
        block = xor(block, tn[i])

        if do_decrypt:
            block = cipher_e.decrypt(block)
        else:
            block = cipher_e.encrypt(block)

        block = xor(block, tn[i])

        decrypted_data += block

    decrypted_data = decrypted_data[::-1]

    with open(data_output_filename, "wb") as f:
        f.write(decrypted_data)


@app.command()
def xts_decrypt(
    data_input_filename: Path,
    tk0: str,
    mk1: str,
    data_output_filename: Path,
):
    """Decrypt the first (flash offset = 0) 128 bits of AEX-XTS encrypted data."""
    raw_tk0 = unhexlify(tk0)
    raw_mk1 = unhexlify(mk1)

    _xts_encrypt_decrypt(
        data_input_filename, raw_tk0, raw_mk1, data_output_filename, do_decrypt=True
    )


@app.command()
def xts_encrypt(
    data_input_filename: Path,
    tk0: str,
    mk1: str,
    data_output_filename: Path,
):
    """Encrypt the first (flash offset = 0) 128 bits of AEX-XTS encrypted data."""
    raw_tk0 = unhexlify(tk0)
    raw_mk1 = unhexlify(mk1)

    _xts_encrypt_decrypt(
        data_input_filename, raw_tk0, raw_mk1, data_output_filename, do_decrypt=False
    )


@app.command()
def process_xts(key_filename: Path):
    """Compute useful derivated keys from a AES-XTS key file."""
    results = {}

    key_data = open(key_filename, "rb").read()

    key_t = key_data[16:]
    key_e = key_data[:16]

    results["Tweak key"] = key_t
    results["Encryption key"] = key_e

    flash_address = 0
    tweak = struct.pack("<I", (flash_address & ~0x7F)) + (b"\x00" * 12)

    cipher_t = AES.new(key_t, AES.MODE_ECB)

    expanded_keys = key_schedule(key_e)
    k0 = expanded_keys[-1]

    results["First decryption round key"] = k0

    for tweak_index in (7, 6):
        tn = cipher_t.encrypt(tweak)
        for _ in range(tweak_index):
            tn = calculate_next_xts_tweak(tn)
        tk = xor(tn, k0)

        results[f"Tweak {tweak_index}"] = tn
        results[f"Tweaked key {tweak_index}"] = tk

    k1 = expanded_keys[-2]
    mk1 = mix_columns_inv(k1)

    results["Second decryption round key"] = k1
    results["Modified second decryption round key"] = mk1

    table = Table(title="AES-XTS derivated keys")
    table.add_column("Name")
    table.add_column("Value")

    for name in results:
        table.add_row(name, results[name].hex())

    print(table)


if __name__ == "__main__":
    app()
