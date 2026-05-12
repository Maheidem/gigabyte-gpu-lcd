from __future__ import annotations

from pathlib import Path

from PIL import Image

from gigabyte_lcd.protocol import LCD_HEIGHT, LCD_WIDTH
from gigabyte_lcd.render import (
    gif_payload,
    parse_color,
    rainbow_color,
    render_gif_frames,
    render_image_file,
    render_rainbow_text_frames,
    render_text,
    rgb565_le,
    single_frame_payload,
)


def test_parse_color() -> None:
    assert parse_color("#ffffff") == (255, 255, 255)
    assert parse_color("0000ff") == (0, 0, 255)


def test_render_text_and_single_frame_payload() -> None:
    image = render_text("LOCAL LLM\nREADY")
    assert image.size == (LCD_WIDTH, LCD_HEIGHT)
    assert len(rgb565_le(image)) == LCD_WIDTH * LCD_HEIGHT * 2
    assert len(single_frame_payload(image)) == 108812


def test_render_image_file_contain(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 128)).save(source)
    image = render_image_file(source, fit="contain", background=(0, 0, 0))
    assert image.size == (LCD_WIDTH, LCD_HEIGHT)


def test_render_gif_payload(tmp_path: Path) -> None:
    gif = tmp_path / "anim.gif"
    frames = [
        Image.new("RGB", (32, 32), "red"),
        Image.new("RGB", (32, 32), "blue"),
    ]
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=80, loop=0)

    rendered, delays = render_gif_frames(gif, max_frames=2)
    assert len(rendered) == 2
    assert delays[0] == 80
    payload = gif_payload(rendered)
    assert payload[:2] == b"\x02\x00"


def test_render_rainbow_text_frames() -> None:
    assert rainbow_color(0) == (255, 0, 0)
    frames = render_rainbow_text_frames("LLM", frame_count=3)
    assert len(frames) == 3
    assert all(frame.size == (LCD_WIDTH, LCD_HEIGHT) for frame in frames)
    assert gif_payload(frames)[:2] == b"\x03\x00"

