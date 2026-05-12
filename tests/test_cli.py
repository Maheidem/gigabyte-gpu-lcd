from __future__ import annotations

from pathlib import Path

from gigabyte_lcd.cli import build_parser, main


def test_send_text_defaults_to_image_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(["send-text", "hello"])
    assert not args.vendor_text_slot
    assert not args.write
    assert args.bus == 3
    assert args.addr == 0x61
    assert args.device_id == 0x21


def test_render_text_command_writes_artifacts(tmp_path: Path) -> None:
    preview = tmp_path / "preview.png"
    payload = tmp_path / "payload.bin"
    result = main(
        [
            "render-text",
            "LOCAL LLM",
            "--preview",
            str(preview),
            "--payload-out",
            str(payload),
        ]
    )
    assert result == 0
    assert preview.exists()
    assert payload.exists()
    assert payload.stat().st_size == 108812


def test_render_status_animated_command_writes_gif_payload(tmp_path: Path) -> None:
    preview = tmp_path / "preview.png"
    payload = tmp_path / "payload.bin"
    result = main(
        [
            "render-status",
            "--animated",
            "--frames",
            "3",
            "--preview",
            str(preview),
            "--payload-out",
            str(payload),
        ]
    )
    assert result == 0
    assert preview.exists()
    assert payload.exists()
    assert payload.read_bytes()[:2] == b"\x03\x00"

