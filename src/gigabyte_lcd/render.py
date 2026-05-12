"""Image rendering helpers for the 320x170 GPU LCD."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence

from .protocol import LCD_HEIGHT, LCD_WIDTH, animation_container, single_frame_container

Color = tuple[int, int, int]


def parse_color(value: str) -> Color:
    text = value.strip().removeprefix("#")
    if len(text) != 6:
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def default_font_path() -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, size)
    candidate = default_font_path()
    if candidate:
        return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def fit_text_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str | None,
    requested_size: int,
    max_width: int,
    max_height: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(requested_size, 9, -1):
        font = load_font(font_path, size)
        box = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="center")
        width = box[2] - box[0]
        height = box[3] - box[1]
        if width <= max_width and height <= max_height:
            return font
    return load_font(font_path, 10)


def render_text(
    text: str,
    foreground: Color = (255, 255, 255),
    background: Color = (0, 0, 0),
    font_path: str | None = None,
    font_size: int = 32,
) -> Image.Image:
    image = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), background)
    draw = ImageDraw.Draw(image)
    font = fit_text_font(draw, text, font_path, font_size, LCD_WIDTH - 20, LCD_HEIGHT - 12)
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="center")
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = (LCD_WIDTH - width) / 2 - box[0]
    y = (LCD_HEIGHT - height) / 2 - box[1]
    draw.multiline_text((x, y), text, fill=foreground, font=font, spacing=4, align="center")
    return image


def rainbow_color(position: float) -> Color:
    """Return a deterministic RGB rainbow sample for a 0..1 position."""

    position = position % 1.0
    segment = int(position * 6)
    fraction = position * 6 - segment
    value = int(255 * fraction)
    if segment == 0:
        return 255, value, 0
    if segment == 1:
        return 255 - value, 255, 0
    if segment == 2:
        return 0, 255, value
    if segment == 3:
        return 0, 255 - value, 255
    if segment == 4:
        return value, 0, 255
    return 255, 0, 255 - value


def render_rainbow_text_frames(
    text: str,
    background: Color = (0, 0, 0),
    font_path: str | None = None,
    font_size: int = 32,
    frame_count: int = 18,
) -> list[Image.Image]:
    """Render moving rainbow text frames for the GIF slot."""

    frame_count = max(2, frame_count)
    mask = Image.new("L", (LCD_WIDTH, LCD_HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    font = fit_text_font(draw, text, font_path, font_size, LCD_WIDTH - 20, LCD_HEIGHT - 12)
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="center")
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = (LCD_WIDTH - width) / 2 - box[0]
    y = (LCD_HEIGHT - height) / 2 - box[1]
    draw.multiline_text((x, y), text, fill=255, font=font, spacing=4, align="center")

    frames = []
    for frame_index in range(frame_count):
        phase = frame_index / frame_count
        gradient = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), background)
        pixels = gradient.load()
        for y_coord in range(LCD_HEIGHT):
            for x_coord in range(LCD_WIDTH):
                pixels[x_coord, y_coord] = rainbow_color((x_coord / LCD_WIDTH) + phase)
        frame = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), background)
        frame.paste(gradient, (0, 0), mask)
        frames.append(frame)
    return frames


def composite_on_background(source: Image.Image, background: Color) -> Image.Image:
    if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
        canvas = Image.new("RGBA", source.size, (*background, 255))
        canvas.alpha_composite(source.convert("RGBA"))
        return canvas.convert("RGB")
    return source.convert("RGB")


def fit_image(source: Image.Image, fit: str = "cover") -> Image.Image:
    if fit == "stretch":
        return source.resize((LCD_WIDTH, LCD_HEIGHT), Image.Resampling.LANCZOS)
    if fit == "contain":
        return ImageOps.contain(source, (LCD_WIDTH, LCD_HEIGHT), Image.Resampling.LANCZOS)
    if fit == "cover":
        return ImageOps.fit(source, (LCD_WIDTH, LCD_HEIGHT), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    raise ValueError(f"unsupported fit mode {fit!r}")


def canvas_image(image: Image.Image, background: Color = (0, 0, 0)) -> Image.Image:
    if image.size == (LCD_WIDTH, LCD_HEIGHT):
        return image.convert("RGB")
    canvas = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), background)
    x = (LCD_WIDTH - image.width) // 2
    y = (LCD_HEIGHT - image.height) // 2
    canvas.paste(image.convert("RGB"), (x, y))
    return canvas


def render_image_file(path: Path, fit: str = "cover", background: Color = (0, 0, 0)) -> Image.Image:
    source = composite_on_background(Image.open(path), background)
    return canvas_image(fit_image(source, fit), background)


def rgb565_le(image: Image.Image) -> bytes:
    image = image.convert("RGB")
    if image.size != (LCD_WIDTH, LCD_HEIGHT):
        raise ValueError(f"expected {LCD_WIDTH}x{LCD_HEIGHT}, got {image.size[0]}x{image.size[1]}")
    payload = bytearray(LCD_WIDTH * LCD_HEIGHT * 2)
    offset = 0
    pixels = image.tobytes()
    for index in range(0, len(pixels), 3):
        red = pixels[index]
        green = pixels[index + 1]
        blue = pixels[index + 2]
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        payload[offset] = value & 0xFF
        payload[offset + 1] = (value >> 8) & 0xFF
        offset += 2
    return bytes(payload)


def single_frame_payload(image: Image.Image) -> bytes:
    return single_frame_container(rgb565_le(image))


def render_gif_frames(
    path: Path,
    fit: str = "cover",
    background: Color = (0, 0, 0),
    max_frames: int = 60,
    frame_step: int = 1,
) -> tuple[list[Image.Image], list[int]]:
    if max_frames < 1:
        raise ValueError("max_frames must be at least 1")
    if frame_step < 1:
        raise ValueError("frame_step must be at least 1")
    source = Image.open(path)
    frames: list[Image.Image] = []
    delays: list[int] = []
    for frame_index, frame in enumerate(ImageSequence.Iterator(source)):
        if frame_index % frame_step:
            continue
        image = composite_on_background(frame.copy(), background)
        frames.append(canvas_image(fit_image(image, fit), background))
        delays.append(int(frame.info.get("duration", source.info.get("duration", 100)) or 100))
        if len(frames) >= max_frames:
            break
    if not frames:
        raise ValueError(f"no frames could be read from {path}")
    return frames, delays


def gif_payload(frames: list[Image.Image]) -> bytes:
    return animation_container([rgb565_le(frame) for frame in frames])
