from __future__ import annotations

import pytest

from gigabyte_lcd.protocol import (
    DisplayMode,
    ImageKind,
    animation_container,
    build_firmware_read_packet,
    build_loop_packet,
    build_metric_overlay_packet,
    build_mode_read_packet,
    build_open_packet,
    build_set_mode_packet,
    build_upload_header_packet,
    gcc_command,
    image_target_address,
    mode_wire_arg,
    padded_packet,
    page_count_for_gcc,
    parse_firmware_response,
    parse_mode_response,
    rle_compress_rgb565_le,
    single_frame_container,
    upload_chunk_mode,
)


def decompress_rle_rgb565(stream: bytes) -> bytes:
    output = bytearray()
    offset = 0
    while offset < len(stream):
        block = int.from_bytes(stream[offset : offset + 2], "little")
        offset += 2
        count = block & 0x7FFF
        if block & 0x8000:
            pixel = stream[offset : offset + 2]
            offset += 2
            output.extend(pixel * count)
        else:
            byte_count = count * 2
            output.extend(stream[offset : offset + byte_count])
            offset += byte_count
    return bytes(output)


def test_padded_packet_and_gcc_prefix() -> None:
    packet = gcc_command(0xD6)
    assert len(packet) == 256
    assert packet[:5] == bytes.fromhex("d6 cb 55 ac 38")
    assert build_firmware_read_packet() == packet
    assert build_mode_read_packet()[:5] == bytes.fromhex("de cb 55 ac 38")


def test_padded_packet_rejects_oversized_input() -> None:
    with pytest.raises(ValueError, match="too large"):
        padded_packet([0] * 257)


def test_mode_wire_arguments() -> None:
    assert mode_wire_arg(DisplayMode.IMAGE) == 4
    assert mode_wire_arg(DisplayMode.TEXT) == 5
    assert mode_wire_arg(DisplayMode.GIF) == 6
    assert mode_wire_arg(DisplayMode.CAROUSEL) == 10
    assert build_open_packet(True)[:6] == bytes.fromhex("e7 cb 55 ac 38 01")
    assert build_open_packet(False)[:6] == bytes.fromhex("e7 cb 55 ac 38 02")
    assert build_set_mode_packet(DisplayMode.IMAGE)[:6] == bytes.fromhex("e5 cb 55 ac 38 04")


def test_overlay_and_loop_packets() -> None:
    overlay = build_metric_overlay_packet(0, 1)
    assert overlay[:5] == bytes.fromhex("e1 cb 55 ac 38")
    assert overlay[5:13] == b"\x00" * 8
    assert overlay[13] == 1

    loop = build_loop_packet([DisplayMode.IMAGE], 1)
    assert loop[:7] == bytes.fromhex("f3 cb 55 ac 38 01 04")


def test_upload_targets_and_header() -> None:
    assert image_target_address(ImageKind.IMAGE, 0x21) == (0x01300000, 1)
    assert image_target_address(ImageKind.TEXT, 0x21) == (0x01320000, 1)
    assert image_target_address(ImageKind.GIF, 0x21) == (0, 2)
    assert image_target_address(ImageKind.IMAGE, 0x10) == (0x01F26000, 1)
    assert image_target_address(ImageKind.TEXT, 0x10) == (0x01F00000, 1)

    header = build_upload_header_packet(
        payload_size=108812,
        kind=ImageKind.IMAGE,
        device_led_id=0x21,
        frame_count=1,
        delay_ms=90,
    )
    assert header[:5] == bytes.fromhex("f1 cb 55 ac 38")
    assert header[5:9] == bytes.fromhex("01 30 00 00")
    assert header[9] == 1
    assert header[10:14] == bytes.fromhex("00 00 01 aa")
    assert header[14:16] == bytes.fromhex("00 01")
    assert header[16] == 90
    assert header[17] == 2
    assert header[18] == 0


def test_page_and_chunk_calculations_match_gcc() -> None:
    assert page_count_for_gcc(108812) == 426
    assert page_count_for_gcc(256) == 2
    assert upload_chunk_mode(20479) == (1, 4096, 0.4)
    assert upload_chunk_mode(20480) == (2, 65536, 2.0)


def test_single_frame_container_header() -> None:
    raw = b"\x00\x00" * (320 * 170)
    payload = single_frame_container(raw)
    assert len(payload) == 108812
    assert payload[:2] == b"\x01\x00"
    assert int.from_bytes(payload[2:6], "little") == 108811
    assert payload[6:12] == bytes.fromhex("40 01 aa 00 01 00")


def test_rle_compression_roundtrip_and_repeat_block() -> None:
    raw = (
        b"\x34\x12" * 5
        + b"\xcd\xab"
        + b"\xde\xbc"
        + b"\xef\xcd" * 4
    )
    compressed = rle_compress_rgb565_le(raw)
    assert decompress_rle_rgb565(compressed) == raw
    assert int.from_bytes(compressed[:2], "little") == 0x8005


def test_animation_container_headers_and_payload_roundtrip() -> None:
    frame_a = b"\x00\xf8" * (320 * 170)
    frame_b = b"\xe0\x07" * (320 * 170)
    payload = animation_container([frame_a, frame_b])
    assert payload[:2] == b"\x02\x00"
    first_end = int.from_bytes(payload[2:6], "little")
    second_end = int.from_bytes(payload[12:16], "little")
    assert payload[6:12] == bytes.fromhex("40 01 aa 00 03 00")
    assert payload[16:22] == bytes.fromhex("40 01 aa 00 03 00")
    assert first_end < second_end


def test_response_parsing() -> None:
    assert parse_firmware_response(bytes.fromhex("d6 14 01 02")) == "F1.4"
    assert parse_mode_response(bytes.fromhex("de 04 01 02")) == (3, True)
    assert parse_mode_response(bytes.fromhex("de 0a 01 02")) == (7, True)
