# Lessons Learned

These notes are the operational lessons from live testing on the RTX 5090
MASTER ICE LCD.

## Exact pixels require image mode

The vendor text slot is not a plain framebuffer. Even after clearing metric
overlay flags with `0xe1`, the text slot could still apply a moving rainbow
effect over uploaded text.

The reliable path for exact output is:

1. Render text into a 320x170 bitmap.
2. Upload it as `ImageKind.IMAGE` to `0x01300000`.
3. Clear metric overlay.
4. Lock carousel to static image mode.
5. Force display mode `3`.

That is why `gigabyte-lcd send-text` and `gigabyte-lcd send-status` default to
image mode. The vendor text slot is only available behind
`send-text --vendor-text-slot`.

## Upload target alone is not enough

Uploading to the static image address does not guarantee the panel shows that
slot. If the panel remains in text or GIF mode, it can keep showing the old
mode. Always force the display mode after upload.

Useful readbacks:

```text
de 04 01 02 -> static image mode enabled
de 05 01 02 -> text mode enabled
de 06 01 02 -> GIF/animation mode enabled
```

## Clear overlays and lock loops

Old carousel slots can rotate back in if `0xf3` is not updated. The package
sets the carousel list to a single mode when applying an upload.

The metric overlay can survive mode changes. The package sends `0xe1` with all
eight flags disabled before forcing the final mode.

## Animation is real GIF mode

The card accepted the recovered RLE animation container and showed a real
animation in GIF mode. Use `send-rainbow-text`, `send-status --animated`, or
`send-gif` when the intended output is animated.

For a static status panel, do not use GIF mode. Use `send-status` without
`--animated`.

## Keep RGB control separate

GPU RGB, motherboard fan RGB, and the LCD are separate devices. The LCD package
should not own motherboard lighting. A future RGB visualizer can read metrics
from Prometheus or local probes and then drive OpenRGB, but it should remain a
separate service from the LCD transport.

## Do not use Docker for local hardware control

This package is local workstation hardware control. It does not manage Docker,
Portainer, Prometheus, or Grafana. Container environment changes should go
through Portainer in the broader homelab workflow, but this LCD work talks
directly to local Linux I2C.

