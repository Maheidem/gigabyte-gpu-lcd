"""High-level LCD device operations."""

from __future__ import annotations

import time

from .protocol import (
    DisplayMode,
    ImageKind,
    Target,
    build_firmware_read_packet,
    build_loop_packet,
    build_metric_overlay_packet,
    build_mode_read_packet,
    build_open_packet,
    build_save_packet,
    build_set_mode_packet,
    build_upload_finish_packet,
    build_upload_header_packet,
    build_upload_start_packet,
    page_count_for_gcc,
    parse_firmware_response,
    parse_mode_response,
    upload_chunk_mode,
)
from .transport import I2CTransport


class GigabyteLcd:
    """Hardware-facing controller for the recovered GCC LCD protocol."""

    def __init__(self, transport: I2CTransport) -> None:
        self.transport = transport

    @classmethod
    def open_target(cls, target: Target, retries: int = 8, retry_delay: float = 0.25) -> "GigabyteLcd":
        return cls(I2CTransport(target, retries=retries, retry_delay=retry_delay))

    def firmware_version(self) -> str:
        data = self.transport.write_read(build_firmware_read_packet(), 4)
        return parse_firmware_response(data)

    def mode(self) -> tuple[int, bool]:
        data = self.transport.write_read(build_mode_read_packet(), 4)
        return parse_mode_response(data)

    def open_lcd(self, enabled: bool = True) -> None:
        self.transport.write(build_open_packet(enabled))

    def set_mode(self, mode: int | DisplayMode) -> None:
        self.transport.write(build_set_mode_packet(mode))

    def clear_metric_overlay(self) -> None:
        self.transport.write(build_metric_overlay_packet(0, 1))

    def set_loop(self, modes: list[int | DisplayMode], interval: int = 1) -> None:
        self.transport.write(build_loop_packet(modes, interval))

    def save(self) -> None:
        self.transport.write(build_save_packet())

    def upload_payload(
        self,
        payload: bytes,
        kind: ImageKind,
        *,
        frame_count: int = 0,
        delay_ms: int = 0,
        progress: bool = False,
    ) -> None:
        """Upload a GCC image/text/GIF payload."""

        self.transport.write(build_upload_start_packet())
        time.sleep(0.5)
        self.transport.write(
            build_upload_header_packet(
                payload_size=len(payload),
                kind=kind,
                device_led_id=self.transport.target.device_led_id,
                frame_count=frame_count,
                delay_ms=delay_ms,
            )
        )

        chunk_mode, chunk_size, prep_delay = upload_chunk_mode(len(payload))
        prep_chunks = (len(payload) + chunk_size - 1) // chunk_size
        for index in range(prep_chunks):
            time.sleep(prep_delay)
            if progress:
                print(f"prepare {index + 1}/{prep_chunks} (mode {chunk_mode})")

        time.sleep(1.0)
        pages = page_count_for_gcc(len(payload))
        for page in range(pages):
            start = page * 256
            block = payload[start : start + 256].ljust(256, b"\x00")
            self.transport.write(block)
            if progress and (page == 0 or page + 1 == pages or (page + 1) % 32 == 0):
                print(f"page {page + 1}/{pages}")
            time.sleep(0.001)

        time.sleep(0.5)
        self.transport.write(build_upload_finish_packet())

    def apply_mode_cleanly(self, mode: int | DisplayMode, save: bool = True) -> None:
        """Clear overlays, lock carousel to one mode, force mode, and optionally save.

        We intentionally set mode twice around save. The panel occasionally kept
        the previous mode after an upload until a second explicit mode command.
        """

        self.clear_metric_overlay()
        self.set_loop([mode], 1)
        self.set_mode(mode)
        time.sleep(0.3)
        if save:
            self.save()
            time.sleep(0.3)
        self.set_mode(mode)
        if save:
            self.save()
