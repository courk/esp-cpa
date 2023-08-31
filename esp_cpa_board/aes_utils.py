#!/usr/bin/env python3
"""Various AES-related helper functions."""
from .aes_lut import GAL9, GAL11, GAL13, GAL14


def _gal_mult128(a, b):
    """Multiply two 128-bit integers using Galois Field arithmetic.

    Args:
        a (int): The first 128-bit integer.
        b (int): The second 128-bit integer.

    Returns:
        int: The result of multiplying a and b using Galois Field arithmetic.

    Note:
        This function performs multiplication using the irreducible polynomial p = (1 << 128) + (1 << 7) + (1 << 2) + (1 << 1) + 1 in the Galois Field GF(2^128).
    """
    result = 0
    p = (1 << 128) + (1 << 7) + (1 << 2) + (1 << 1) + 1
    for i in range(128):
        result = result << 1
        if (b >> (128 - i - 1)) & 1:
            result = result ^ a
        if result >> 128:
            result = result ^ p
    return result


def calculate_next_xts_tweak(tweak: bytes) -> bytes:
    """Calculates the next tweak value.

    Args:
        tweak (bytes): The current tweak value as bytes.

    Returns:
        bytes: The next tweak value as bytes.
    """
    tweak_n = int.from_bytes(tweak, byteorder="little")
    next_tweak_n = _gal_mult128(tweak_n, 2)
    next_tweak = next_tweak_n.to_bytes(16, byteorder="little")

    return next_tweak


def calculate_previous_xts_tweak(tweak: bytes) -> bytes:
    """Calculate the previous tweak value.

    Args:
        tweak (bytes): The tweak value as bytes.

    Returns:
        bytes: The previous tweak value as bytes.
    """
    tweak_n = int.from_bytes(tweak, byteorder="little")
    next_tweak_n = _gal_mult128(
        tweak_n, 0x80000000000000000000000000000043  # Inverse of 2 in GF(2**128)
    )
    next_tweak = next_tweak_n.to_bytes(16, byteorder="little")

    return next_tweak


def xor(a: bytes, b: bytes) -> bytes:
    """Performs XOR operation on two byte sequences.

    Args:
        a (bytes): First byte sequence
        b (bytes): Second byte sequence

    Returns:
        bytes: The result of XOR operation as a byte sequence.
    """
    return bytes([x ^ y for x, y in zip(a, b)])


def _mix_column_inv(data: bytes) -> bytes:
    """Mixes the columns of a 4-byte data block using the inverse MixColumns operation.

    Args:
        data (bytes): The input data block as a bytes object.

    Returns:
        bytes: The result of the inverse MixColumns operation as a bytes object.
    """
    result = [0] * 4

    result[0] = GAL14[data[0]] ^ GAL9[data[3]] ^ GAL13[data[2]] ^ GAL11[data[1]]
    result[1] = GAL14[data[1]] ^ GAL9[data[0]] ^ GAL13[data[3]] ^ GAL11[data[2]]
    result[2] = GAL14[data[2]] ^ GAL9[data[1]] ^ GAL13[data[0]] ^ GAL11[data[3]]
    result[3] = GAL14[data[3]] ^ GAL9[data[2]] ^ GAL13[data[1]] ^ GAL11[data[0]]

    return bytes(result)


def _mix_column(data: bytes) -> bytes:
    """Mixes the columns of a 4-byte data block.

    Args:
        data (bytes): The input data block as bytes.

    Returns:
        bytes: The result of mixing the columns as bytes.
    """
    result = [0] * 4

    a = [0] * 4
    b = [0] * 4

    for i in range(4):
        a[i] = data[i]
        h = (data[i] >> 7) & 0xFF
        b[i] = (data[i] << 1) & 0xFF
        b[i] ^= 0x1B * h

    result[0] = b[0] ^ a[3] ^ a[2] ^ b[1] ^ a[1]
    result[1] = b[1] ^ a[0] ^ a[3] ^ b[2] ^ a[2]
    result[2] = b[2] ^ a[1] ^ a[0] ^ b[3] ^ a[3]
    result[3] = b[3] ^ a[2] ^ a[1] ^ b[0] ^ a[0]

    return bytes(result)


def mix_columns_inv(data: bytes) -> bytes:
    """Mix the columns of a 16-byte data block using the inverse mix column operation.

    Args:
        data (bytes): The input data block as bytes.

    Returns:
        bytes: The result of mixing the columns as bytes.
    """
    result = [0] * 16
    for i in range(4):
        col = data[i * 4 : (i + 1) * 4]
        col = _mix_column_inv(col)
        for j, b in enumerate(col):
            result[i * 4 + j] = b
    return bytes(result)


def mix_columns(data: bytes) -> bytes:
    """Mix the columns of a 16-byte data block.

    Args:
        data (bytes): The input data block as bytes.

    Returns:
        bytes: The resulting data block after mixing the columns.
    """
    result = [0] * 16
    for i in range(4):
        col = data[i * 4 : (i + 1) * 4]
        col = _mix_column(col)
        for j, b in enumerate(col):
            result[i * 4 + j] = b
    return bytes(result)
