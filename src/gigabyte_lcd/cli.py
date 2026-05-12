"""Command-line interface for gigabyte-gpu-lcd."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .device import GigabyteLcd
from .protocol import DisplayMode, ImageKind, Target
from .render import (
    gif_payload,
    parse_color,
    render_gif_frames,
    render_image_file,
    render_rainbow_text_frames,
    render_text,
    single_frame_payload,
)
from .status import inference_status_text


def target_from_args(args: argparse.Namespace) -> Target:
    return Target(bus=args.bus, addr=args.addr, device_led_id=args.device_id)


def lcd_from_args(args: argparse.Namespace) -> GigabyteLcd:
    return GigabyteLcd.open_target(target_from_args(args), retries=args.retries, retry_delay=args.retry_delay)


def write_artifacts(image, payload: bytes, preview: Path | None, payload_out: Path | None) -> None:
    if preview:
        preview.parent.mkdir(parents=True, exist_ok=True)
        image.save(preview)
        print(f"preview: {preview}")
    if payload_out:
        payload_out.parent.mkdir(parents=True, exist_ok=True)
        payload_out.write_bytes(payload)
        print(f"payload: {payload_out} ({len(payload)} bytes)")


def apply_payload(
    args: argparse.Namespace,
    image,
    payload: bytes,
    kind: ImageKind,
    mode: DisplayMode,
    *,
    label: str,
    frame_count: int = 0,
    delay_ms: int = 0,
) -> int:
    write_artifacts(image, payload, args.preview, args.payload_out)
    if not args.write:
        print("dry run: add --write to upload to the GPU LCD")
        return 0
    lcd = lcd_from_args(args)
    print(f"target: {lcd.transport.target.path} addr 0x{lcd.transport.target.addr:02x}")
    print(f"firmware: {lcd.firmware_version()}")
    print(f"uploading {label}: {len(payload)} bytes")
    lcd.open_lcd(True)
    lcd.upload_payload(payload, kind, frame_count=frame_count, delay_ms=delay_ms, progress=True)
    if not args.no_apply:
        lcd.apply_mode_cleanly(mode, save=not args.no_save)
    print("done")
    return 0


def command_probe(args: argparse.Namespace) -> int:
    lcd = lcd_from_args(args)
    print(f"target: {lcd.transport.target.path} addr 0x{lcd.transport.target.addr:02x}")
    print(f"firmware: {lcd.firmware_version()}")
    mode, enabled = lcd.mode()
    print(f"mode: {mode} enabled={enabled}")
    return 0


def command_clear_overlay(args: argparse.Namespace) -> int:
    lcd = lcd_from_args(args)
    print(f"target: {lcd.transport.target.path} addr 0x{lcd.transport.target.addr:02x}")
    print(f"firmware: {lcd.firmware_version()}")
    if not args.write:
        print("dry run: add --write to clear overlay")
        return 0
    lcd.open_lcd(True)
    lcd.clear_metric_overlay()
    if args.mode is not None:
        lcd.apply_mode_cleanly(DisplayMode(args.mode), save=not args.no_save)
    elif not args.no_save:
        lcd.save()
    print("done")
    return 0


def command_render_text(args: argparse.Namespace) -> int:
    image = render_text(args.text, args.foreground, args.background, args.font, args.font_size)
    payload = single_frame_payload(image)
    write_artifacts(image, payload, args.preview, args.payload_out)
    return 0


def command_send_text(args: argparse.Namespace) -> int:
    image = render_text(args.text, args.foreground, args.background, args.font, args.font_size)
    payload = single_frame_payload(image)
    if args.vendor_text_slot:
        return apply_payload(args, image, payload, ImageKind.TEXT, DisplayMode.TEXT, label="vendor text")
    return apply_payload(args, image, payload, ImageKind.IMAGE, DisplayMode.IMAGE, label="text-as-image")


def command_render_image(args: argparse.Namespace) -> int:
    image = render_image_file(args.image, args.fit, args.background)
    payload = single_frame_payload(image)
    write_artifacts(image, payload, args.preview, args.payload_out)
    return 0


def command_send_image(args: argparse.Namespace) -> int:
    image = render_image_file(args.image, args.fit, args.background)
    payload = single_frame_payload(image)
    return apply_payload(args, image, payload, ImageKind.IMAGE, DisplayMode.IMAGE, label="image")


def command_render_gif(args: argparse.Namespace) -> int:
    frames, delays = render_gif_frames(args.gif, args.fit, args.background, args.max_frames, args.frame_step)
    payload = gif_payload(frames)
    write_artifacts(frames[0], payload, args.preview, args.payload_out)
    print(f"frames: {len(frames)}, first delay: {delays[0]} ms")
    return 0


def command_send_gif(args: argparse.Namespace) -> int:
    frames, delays = render_gif_frames(args.gif, args.fit, args.background, args.max_frames, args.frame_step)
    payload = gif_payload(frames)
    print(f"frames: {len(frames)}, first delay: {delays[0]} ms")
    return apply_payload(
        args,
        frames[0],
        payload,
        ImageKind.GIF,
        DisplayMode.GIF,
        label="gif",
        frame_count=len(frames),
        delay_ms=delays[0],
    )


def command_render_rainbow_text(args: argparse.Namespace) -> int:
    frames = render_rainbow_text_frames(args.text, args.background, args.font, args.font_size, args.frames)
    payload = gif_payload(frames)
    write_artifacts(frames[0], payload, args.preview, args.payload_out)
    print(f"frames: {len(frames)}, delay: {args.delay_ms} ms")
    return 0


def command_send_rainbow_text(args: argparse.Namespace) -> int:
    frames = render_rainbow_text_frames(args.text, args.background, args.font, args.font_size, args.frames)
    payload = gif_payload(frames)
    print(f"frames: {len(frames)}, delay: {args.delay_ms} ms")
    return apply_payload(
        args,
        frames[0],
        payload,
        ImageKind.GIF,
        DisplayMode.GIF,
        label="rainbow text",
        frame_count=len(frames),
        delay_ms=args.delay_ms,
    )


def command_render_status(args: argparse.Namespace) -> int:
    text = inference_status_text()
    print(text)
    if args.animated:
        frames = render_rainbow_text_frames(text, args.background, args.font, args.font_size, args.frames)
        payload = gif_payload(frames)
        write_artifacts(frames[0], payload, args.preview, args.payload_out)
        print(f"frames: {len(frames)}, delay: {args.delay_ms} ms")
        return 0
    image = render_text(text, args.foreground, args.background, args.font, args.font_size)
    payload = single_frame_payload(image)
    write_artifacts(image, payload, args.preview, args.payload_out)
    return 0


def command_send_status(args: argparse.Namespace) -> int:
    text = inference_status_text()
    print(text)
    if args.animated:
        frames = render_rainbow_text_frames(text, args.background, args.font, args.font_size, args.frames)
        payload = gif_payload(frames)
        print(f"frames: {len(frames)}, delay: {args.delay_ms} ms")
        return apply_payload(
            args,
            frames[0],
            payload,
            ImageKind.GIF,
            DisplayMode.GIF,
            label="rainbow status",
            frame_count=len(frames),
            delay_ms=args.delay_ms,
        )
    image = render_text(text, args.foreground, args.background, args.font, args.font_size)
    payload = single_frame_payload(image)
    return apply_payload(args, image, payload, ImageKind.IMAGE, DisplayMode.IMAGE, label="status-as-image")


def parse_color_arg(value: str) -> tuple[int, int, int]:
    try:
        return parse_color(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bus", type=int, default=3, help="Linux I2C bus number")
    parser.add_argument("--addr", type=lambda value: int(value, 0), default=0x61, help="7-bit I2C address")
    parser.add_argument("--device-id", type=lambda value: int(value, 0), default=0x21, help="GCC simple device id")
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--retry-delay", type=float, default=0.25)


def add_render_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preview", type=Path, default=Path("gpu-lcd-preview.png"))
    parser.add_argument("--payload-out", type=Path, default=Path("gpu-lcd-payload.bin"))


def add_send_args(parser: argparse.ArgumentParser) -> None:
    add_target_args(parser)
    add_render_args(parser)
    parser.add_argument("--write", action="store_true", help="actually write to the GPU LCD")
    parser.add_argument("--no-save", action="store_true", help="skip GCC save command")
    parser.add_argument("--no-apply", action="store_true", help="skip overlay clear, loop lock, and mode switch")


def add_text_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("text")
    parser.add_argument("--foreground", type=parse_color_arg, default=(255, 255, 255))
    parser.add_argument("--background", type=parse_color_arg, default=(0, 0, 0))
    parser.add_argument("--font", default=None)
    parser.add_argument("--font-size", type=int, default=32)


def add_image_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("image", type=Path)
    parser.add_argument("--fit", choices=("cover", "contain", "stretch"), default="cover")
    parser.add_argument("--background", type=parse_color_arg, default=(0, 0, 0))


def add_gif_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("gif", type=Path)
    parser.add_argument("--fit", choices=("cover", "contain", "stretch"), default="cover")
    parser.add_argument("--background", type=parse_color_arg, default=(0, 0, 0))
    parser.add_argument("--max-frames", type=int, default=60)
    parser.add_argument("--frame-step", type=int, default=1)


def add_animation_text_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("text")
    parser.add_argument("--background", type=parse_color_arg, default=(0, 0, 0))
    parser.add_argument("--font", default=None)
    parser.add_argument("--font-size", type=int, default=32)
    parser.add_argument("--frames", type=int, default=18)
    parser.add_argument("--delay-ms", type=int, default=90)


def add_status_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--animated", action="store_true", help="render status as GIF-mode rainbow text")
    parser.add_argument("--foreground", type=parse_color_arg, default=(255, 255, 255))
    parser.add_argument("--background", type=parse_color_arg, default=(0, 0, 0))
    parser.add_argument("--font", default=None)
    parser.add_argument("--font-size", type=int, default=30)
    parser.add_argument("--frames", type=int, default=18)
    parser.add_argument("--delay-ms", type=int, default=90)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control Gigabyte AORUS GPU LCD panels on Linux")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe")
    add_target_args(probe)
    probe.set_defaults(func=command_probe)

    clear_overlay = subparsers.add_parser("clear-overlay")
    add_target_args(clear_overlay)
    clear_overlay.add_argument("--write", action="store_true")
    clear_overlay.add_argument("--no-save", action="store_true")
    clear_overlay.add_argument("--mode", type=int, choices=range(0, 8), default=None)
    clear_overlay.set_defaults(func=command_clear_overlay)

    render_text = subparsers.add_parser("render-text")
    add_text_args(render_text)
    add_render_args(render_text)
    render_text.set_defaults(func=command_render_text)

    send_text = subparsers.add_parser("send-text")
    add_text_args(send_text)
    send_text.add_argument("--vendor-text-slot", action="store_true", help="use GCC text slot instead of image mode")
    add_send_args(send_text)
    send_text.set_defaults(func=command_send_text)

    render_image = subparsers.add_parser("render-image")
    add_image_args(render_image)
    add_render_args(render_image)
    render_image.set_defaults(func=command_render_image)

    send_image = subparsers.add_parser("send-image")
    add_image_args(send_image)
    add_send_args(send_image)
    send_image.set_defaults(func=command_send_image)

    render_gif = subparsers.add_parser("render-gif")
    add_gif_args(render_gif)
    add_render_args(render_gif)
    render_gif.set_defaults(func=command_render_gif)

    render_rainbow_text = subparsers.add_parser("render-rainbow-text")
    add_animation_text_args(render_rainbow_text)
    add_render_args(render_rainbow_text)
    render_rainbow_text.set_defaults(func=command_render_rainbow_text)

    send_gif = subparsers.add_parser("send-gif")
    add_gif_args(send_gif)
    add_send_args(send_gif)
    send_gif.set_defaults(func=command_send_gif)

    send_rainbow_text = subparsers.add_parser("send-rainbow-text")
    add_animation_text_args(send_rainbow_text)
    add_send_args(send_rainbow_text)
    send_rainbow_text.set_defaults(func=command_send_rainbow_text)

    render_status = subparsers.add_parser("render-status")
    add_status_args(render_status)
    add_render_args(render_status)
    render_status.set_defaults(func=command_render_status)

    send_status = subparsers.add_parser("send-status")
    add_status_args(send_status)
    add_send_args(send_status)
    send_status.set_defaults(func=command_send_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
