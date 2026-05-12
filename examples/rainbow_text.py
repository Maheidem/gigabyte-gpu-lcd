#!/usr/bin/env python3
"""Render rainbow text frames to a GCC GIF-mode payload."""

from pathlib import Path

from gigabyte_lcd.render import gif_payload, render_rainbow_text_frames


def main() -> None:
    frames = render_rainbow_text_frames("LOCAL LLM READY", frame_count=18)
    frames[0].save("rainbow-preview.png")
    Path("rainbow-payload.bin").write_bytes(gif_payload(frames))
    print(f"frames: {len(frames)}")


if __name__ == "__main__":
    main()

