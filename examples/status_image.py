#!/usr/bin/env python3
"""Render the local inference status to a preview image and payload."""

from pathlib import Path

from gigabyte_lcd.render import render_text, single_frame_payload
from gigabyte_lcd.status import inference_status_text


def main() -> None:
    text = inference_status_text()
    image = render_text(text)
    image.save("status-preview.png")
    Path("status-payload.bin").write_bytes(single_frame_payload(image))
    print(text)


if __name__ == "__main__":
    main()

