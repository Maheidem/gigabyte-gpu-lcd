# gigabyte-gpu-lcd

Linux control library and CLI for the LCD on Gigabyte AORUS GPUs.

This repository captures the working protocol recovered on a Gigabyte AORUS
GeForce RTX 5090 MASTER ICE. The tested LCD controller is on Linux I2C bus
`/dev/i2c-3`, 7-bit address `0x61`, and reports firmware `F1.4`.

The package intentionally renders normal text and status screens into the
static image slot. On the tested card, the vendor text slot can apply panel-side
effects over the uploaded pixels. Static image mode is the reliable path for
exact white text on a black background.

## Status

- Tested hardware: Gigabyte AORUS GeForce RTX 5090 MASTER ICE 32G.
- Protocol family: old GCC `GvLcdApi`, not the newer `GvLcdExApi`.
- Static image uploads: working.
- GIF/RLE animation uploads: working.
- Vendor metric overlay clearing: working.
- Vendor text slot: mapped, but not recommended for exact output.
- Published repository: <https://github.com/Maheidem/gigabyte-gpu-lcd>.

No Gigabyte binaries, assets, or firmware are included.

## Install locally

```bash
cd ~/gigabyte-gpu-lcd
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Most hardware writes need permission to open `/dev/i2c-N`. Use root, sudo, or an
appropriate local udev/i2c group rule.

## Probe the LCD

```bash
sudo -E .venv/bin/gigabyte-lcd probe
```

Expected on the tested RTX 5090:

```text
target: /dev/i2c-3 addr 0x61
firmware: F1.4
```

## Send exact text

This renders the text into a 320x170 bitmap, uploads it to the static image
slot at `0x01300000`, clears the metric overlay, locks the carousel to image
mode, and forces display mode `3`.

```bash
sudo -E .venv/bin/gigabyte-lcd send-text $'LOCAL LLM\nREADY' --write
```

Use this path for status screens and anything where exact pixels matter.

## Send local inference status

```bash
sudo -E .venv/bin/gigabyte-lcd send-status --write
```

The status renderer checks local OpenAI-compatible model endpoints, process CPU,
and `nvidia-smi`:

- vLLM model endpoint: `127.0.0.1:8082/v1/models`
- llama.cpp model endpoint: `127.0.0.1:8081/v1/models`
- proxy fallback endpoint: `127.0.0.1:8080/v1/models`
- GPU VRAM and watts: `nvidia-smi`

The panel text layout is:

```text
<engine>
<model>
CPU <percent>% VRAM <GiB>G
PWR <watts>W
```

## Send animation

```bash
sudo -E .venv/bin/gigabyte-lcd send-rainbow-text "LOCAL LLM READY" --write
sudo -E .venv/bin/gigabyte-lcd send-status --animated --write
sudo -E .venv/bin/gigabyte-lcd send-gif /path/to/animation.gif --max-frames 60 --write
```

Animated commands upload an RLE GIF payload and force display mode `5`.

## Render without touching hardware

Every renderer writes a PNG preview and binary payload by default:

```bash
.venv/bin/gigabyte-lcd render-text $'LOCAL LLM\nREADY'
.venv/bin/gigabyte-lcd render-status
.venv/bin/gigabyte-lcd render-status --animated
.venv/bin/gigabyte-lcd render-image /path/to/image.png
.venv/bin/gigabyte-lcd render-gif /path/to/animation.gif --max-frames 12
```

Use `--preview` and `--payload-out` to choose output paths.

## Safety notes

- This talks directly to GPU-attached I2C. Use it only on hardware you control.
- The default target is the tested card: `--bus 3 --addr 0x61 --device-id 0x21`.
- Do not assume other Gigabyte GPU generations use the same bus, address, or
  upload addresses.
- `--write` is required before the CLI sends any LCD upload.
- `send-text --vendor-text-slot` exists only for protocol testing. It can show a
  rainbow/effect overlay on the tested card even after metric overlay flags are
  cleared.

## Documentation

- [Protocol](docs/protocol.md)
- [Hardware notes](docs/hardware-notes.md)
- [Lessons learned](docs/lessons-learned.md)
- [Publishing checklist](docs/publish.md)
