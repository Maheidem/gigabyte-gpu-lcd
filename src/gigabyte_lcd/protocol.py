"""Pure packet and payload helpers for the Gigabyte GPU LCD protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

LCD_WIDTH = 320
LCD_HEIGHT = 170
I2C_PAGE_SIZE = 256
DEFAULT_BUS = 3
DEFAULT_ADDR = 0x61
DEFAULT_DEVICE_LED_ID = 0x21
GCC_MAGIC = (0xCB, 0x55, 0xAC, 0x38)

FIFTY_SERIES_LCD_IDS = {0x18, 0x19, 0x20, 0x21, 0x22}


class ImageKind(IntEnum):
    """Image type byte used in the GCC upload header."""

    GIF = 0
    IMAGE = 1
    TEXT = 2


class DisplayMode(IntEnum):
    """GCC LCD display modes recovered from ucVga.Models.GvLcd.DisplayMode."""

    FAITH1 = 0
    FAITH2 = 1
    FAITH3 = 2
    IMAGE = 3
    TEXT = 4
    GIF = 5
    CHIBI_TIME = 6
    CAROUSEL = 7


@dataclass(frozen=True)
class Target:
    """Linux I2C target for the LCD controller."""

    bus: int = DEFAULT_BUS
    addr: int = DEFAULT_ADDR
    device_led_id: int = DEFAULT_DEVICE_LED_ID

    @property
    def path(self) -> str:
        return f"/dev/i2c-{self.bus}"


def padded_packet(data: Iterable[int], size: int = I2C_PAGE_SIZE) -> bytes:
    """Return a fixed-size I2C packet padded with zeroes."""

    packet = bytearray(size)
    values = bytes(data)
    if len(values) > size:
        raise ValueError(f"packet is too large: {len(values)} > {size}")
    packet[: len(values)] = values
    return bytes(packet)


def gcc_command(opcode: int, *args: int) -> bytes:
    """Build a 256-byte command packet with the GCC magic prefix."""

    return padded_packet((opcode, *GCC_MAGIC, *args))


def u16be(value: int) -> tuple[int, int]:
    return ((value >> 8) & 0xFF, value & 0xFF)


def u32be(value: int) -> tuple[int, int, int, int]:
    return (
        (value >> 24) & 0xFF,
        (value >> 16) & 0xFF,
        (value >> 8) & 0xFF,
        value & 0xFF,
    )


def mode_wire_arg(mode: int | DisplayMode) -> int:
    """Convert a display mode enum into the argument GCC sends to 0xE5."""

    mode_value = int(mode)
    if mode_value == DisplayMode.CAROUSEL:
        mode_value = 9
    return mode_value + 1


def build_open_packet(enabled: bool) -> bytes:
    return gcc_command(0xE7, 0x01 if enabled else 0x02)


def build_set_mode_packet(mode: int | DisplayMode) -> bytes:
    return gcc_command(0xE5, mode_wire_arg(mode))


def build_save_packet() -> bytes:
    return gcc_command(0xAA)


def build_firmware_read_packet() -> bytes:
    return gcc_command(0xD6)


def build_mode_read_packet() -> bytes:
    return gcc_command(0xDE)


def build_metric_overlay_packet(flags: int = 0, interval: int = 1) -> bytes:
    """Build the 0xE1 metric overlay packet.

    Flags use the vendor bit order: GPU temperature, clock, usage, fan speed,
    VRAM clock, VRAM usage, FPS, and TGP/power.
    """

    payload = [0xE1, *GCC_MAGIC]
    for bit in range(8):
        payload.append(1 if flags & (1 << bit) else 0)
    payload.append(max(1, min(255, interval)))
    return padded_packet(payload)


def build_loop_packet(modes: list[int | DisplayMode], interval: int = 1) -> bytes:
    """Build the 0xF3 carousel packet."""

    payload = [0xF3, *GCC_MAGIC, max(1, min(255, interval))]
    for mode in modes[:24]:
        mode_value = int(mode)
        if mode_value <= 6:
            payload.append(mode_value + 1)
    return padded_packet(payload)


def image_target_address(kind: ImageKind, device_led_id: int) -> tuple[int, int]:
    """Return ``(address, storage_type)`` for the upload header."""

    if kind == ImageKind.IMAGE:
        return (0x01300000 if device_led_id in FIFTY_SERIES_LCD_IDS else 0x01F26000, 1)
    if kind == ImageKind.TEXT:
        return (0x01320000 if device_led_id in FIFTY_SERIES_LCD_IDS else 0x01F00000, 1)
    if kind == ImageKind.GIF:
        return (0, 2)
    raise ValueError(f"unsupported image kind {kind!r}")


def page_count_for_gcc(byte_count: int) -> int:
    """Return GCC's page count, including its extra page for exact multiples."""

    return byte_count // I2C_PAGE_SIZE + 1


def upload_chunk_mode(byte_count: int) -> tuple[int, int, float]:
    """Return ``(mode_byte, preparation_chunk_size, preparation_sleep_seconds)``."""

    if byte_count < 20480:
        return 1, 4096, 0.4
    return 2, 65536, 2.0


def build_upload_start_packet() -> bytes:
    return gcc_command(0xF2, 0x01)


def build_upload_finish_packet() -> bytes:
    return gcc_command(0xF2, 0x02)


def build_upload_header_packet(
    *,
    payload_size: int,
    kind: ImageKind,
    device_led_id: int,
    frame_count: int = 0,
    delay_ms: int = 0,
) -> bytes:
    target_address, storage_type = image_target_address(kind, device_led_id)
    page_count = page_count_for_gcc(payload_size)
    chunk_mode, _, _ = upload_chunk_mode(payload_size)
    return gcc_command(
        0xF1,
        *u32be(target_address),
        storage_type,
        *u32be(page_count),
        *u16be(frame_count),
        min(255, max(0, delay_ms)),
        chunk_mode,
        0,
    )


def single_frame_container(rgb565_le: bytes, width: int = LCD_WIDTH, height: int = LCD_HEIGHT) -> bytes:
    """Wrap raw little-endian RGB565 pixels in GCC's single-frame container."""

    expected = width * height * 2
    if len(rgb565_le) != expected:
        raise ValueError(f"expected {expected} RGB565 bytes, got {len(rgb565_le)}")
    frame_count = 1
    header_len = 2 + frame_count * 10
    end_offset_minus_one = header_len + len(rgb565_le) - 1
    return b"".join(
        [
            frame_count.to_bytes(2, "little"),
            end_offset_minus_one.to_bytes(4, "little"),
            width.to_bytes(2, "little"),
            height.to_bytes(2, "little"),
            (1).to_bytes(2, "little"),
            rgb565_le,
        ]
    )


def find_rle_block(values: list[int], start: int) -> tuple[int, int]:
    """Return ``(literal_count, repeated_count)`` matching RLE_Compress.dll."""

    segment_end = min(len(values), start + 32767)
    segment = values[start:segment_end]
    if len(segment) < 4:
        return len(segment), 0

    index = 0
    while index < len(segment):
        if index + 2 == len(segment):
            return len(segment), 0
        if segment[index] == segment[index + 1] == segment[index + 2]:
            run_start = index
            index += 2
            while index < len(segment) - 1 and segment[index] == segment[index + 1]:
                index += 1
            return run_start, index + 1 - run_start
        index += 1

    return len(segment), 0


def rle_compress_rgb565_le(rgb565_le: bytes) -> bytes:
    """Compress little-endian RGB565 bytes using the vendor RLE format."""

    if len(rgb565_le) % 2:
        raise ValueError("RGB565 payload must have an even byte count")
    values = [
        rgb565_le[index] | (rgb565_le[index + 1] << 8)
        for index in range(0, len(rgb565_le), 2)
    ]
    output = bytearray()
    index = 0

    while index < len(values):
        literal_count, repeated_count = find_rle_block(values, index)
        if literal_count:
            output.extend(literal_count.to_bytes(2, "little"))
            for value in values[index : index + literal_count]:
                output.append(value & 0xFF)
                output.append((value >> 8) & 0xFF)
        if repeated_count:
            output.extend((repeated_count | 0x8000).to_bytes(2, "little"))
            value = values[index + literal_count]
            output.append(value & 0xFF)
            output.append((value >> 8) & 0xFF)
        index += literal_count + repeated_count

    return bytes(output)


def animation_container(
    frame_rgb565_le: list[bytes],
    width: int = LCD_WIDTH,
    height: int = LCD_HEIGHT,
) -> bytes:
    """Build GCC's RLE multi-frame animation container."""

    if not frame_rgb565_le:
        raise ValueError("animation must contain at least one frame")
    expected = width * height * 2
    streams = []
    for frame in frame_rgb565_le:
        if len(frame) != expected:
            raise ValueError(f"expected {expected} RGB565 bytes, got {len(frame)}")
        streams.append(rle_compress_rgb565_le(frame))

    offset = 2 + len(streams) * 10
    headers = []
    for stream in streams:
        offset += len(stream)
        headers.append(
            b"".join(
                [
                    (offset - 1).to_bytes(4, "little"),
                    width.to_bytes(2, "little"),
                    height.to_bytes(2, "little"),
                    (3).to_bytes(2, "little"),
                ]
            )
        )
    return b"".join([len(streams).to_bytes(2, "little"), *headers, *streams])


def parse_firmware_response(data: bytes) -> str:
    if len(data) < 2:
        raise ValueError(f"short firmware response: {data.hex(' ')}")
    return f"F{data[1] >> 4}.{data[1] & 0x0F}"


def parse_mode_response(data: bytes) -> tuple[int, bool]:
    if len(data) < 3:
        raise ValueError(f"short mode response: {data.hex(' ')}")
    mode = data[1] - 1
    if mode == 9:
        mode = DisplayMode.CAROUSEL
    return int(mode), data[2] == 1
