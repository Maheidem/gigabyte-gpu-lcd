# Protocol

This document records the recovered old Gigabyte Control Center LCD protocol
used by the tested Gigabyte AORUS GeForce RTX 5090 MASTER ICE.

## Transport

The LCD controller answers on the NVIDIA I2C adapter exposed at:

```text
/dev/i2c-3
7-bit address: 0x61
8-bit write address used by GCC internals: 0xc2
```

GCC uses 256-byte I2C messages. Commands are padded with zero bytes to exactly
256 bytes and begin with:

```text
<opcode> cb 55 ac 38 ...
```

The useful newer `GvLcdExApi` probe at address `0x76` did not answer on the
tested card. The working path is the older `GvLcdApi` protocol at `0x61`.

## Known commands

| Opcode | Meaning | Notes |
| --- | --- | --- |
| `0xd6` | Read firmware | Response observed: `d6 14 01 02`; byte `0x14` parses as `F1.4`. |
| `0xde` | Read current mode | Response includes mode byte and enabled byte. |
| `0xe7` | Open/close LCD | Arg `0x01` enables, `0x02` disables. |
| `0xe5` | Set display mode | Arg is `mode + 1`; carousel mode `7` is sent as wire mode `9`, arg `10`. |
| `0xe1` | Set metric overlay flags | Eight flag bytes, then interval. All zero flag bytes clear the vendor metrics overlay. |
| `0xf3` | Set carousel/loop list | Use a single mode to prevent old slots from rotating in. |
| `0xf2 0x01` | Start upload | Sent before the upload header. |
| `0xf1` | Upload header | Contains target address, storage type, page count, frame count, delay, and chunk mode. |
| raw page | Upload payload page | 256-byte pages, padded on the final page. |
| `0xf2 0x02` | Finish upload | Sent after all payload pages. |
| `0xaa` | Save | Persists display settings. |

## Display modes

The mode enum was recovered from GCC's managed VGA module:

| Mode | Name | Observed readback |
| --- | --- | --- |
| `0` | Faith1 | Not validated. |
| `1` | Faith2 | Not validated. |
| `2` | Faith3 | Not validated. |
| `3` | Static image | `de 04 01 02` means image mode enabled. |
| `4` | Text | `de 05 01 02` means text mode enabled. |
| `5` | GIF/animation | `de 06 01 02` means GIF mode enabled. |
| `6` | ChibiTime | Not validated. |
| `7` | Carousel | Set command uses wire mode `9`, arg `10`. |

## Metric overlay

The `0xe1` command controls the vendor overlay. The eight flags are in the GCC
order:

```text
GPU temperature
GPU clock
GPU usage
fan speed
VRAM clock
VRAM usage
FPS
TGP / power
```

Sending all flag bytes as `0` cleared the overlay on the tested card. Readback
changed from `df 80 01 02` to `df 00 01 02`.

Important distinction: this only clears the vendor metric overlay. It does not
disable every panel-side effect for every slot. The vendor text slot can still
apply a moving effect over uploaded text.

## Upload header

After `0xf2 0x01`, GCC sends an `0xf1` header:

```text
f1 cb 55 ac 38
<target address u32 big-endian>
<storage type u8>
<page count u32 big-endian>
<frame count u16 big-endian>
<delay ms u8>
<chunk mode u8>
00
```

The page count is `payload_size // 256 + 1`. GCC keeps the extra page even when
the payload size is an exact multiple of 256.

Chunk mode:

| Payload size | Mode byte | Prep chunk size | Prep delay |
| --- | --- | --- | --- |
| `< 20480` bytes | `1` | 4096 bytes | 0.4 seconds |
| `>= 20480` bytes | `2` | 65536 bytes | 2.0 seconds |

## Upload targets

For this card's GCC device id `0x21`:

| Payload kind | Target address | Storage type | Display mode |
| --- | --- | --- | --- |
| Static image | `0x01300000` | `1` | `3` |
| Vendor text slot | `0x01320000` | `1` | `4` |
| GIF/RLE animation | `0x00000000` | `2` | `5` |

Older/non-50-series GCC ids use different image/text addresses in GCC:

| Payload kind | Target address |
| --- | --- |
| Static image | `0x01f26000` |
| Vendor text slot | `0x01f00000` |

Only the 50-series `0x21` path has been validated here.

## Static image container

Static image and vendor text uploads use the same single-frame container with
uncompressed little-endian RGB565 pixels:

```text
u16 frame_count = 1
u32 frame_end_offset_minus_one
u16 width = 320
u16 height = 170
u16 image_format = 1
RGB565 little-endian pixels, 320 * 170 * 2 bytes
```

Total size for a full panel is `108812` bytes.

## Animation container

GIF mode uses a multi-frame RLE container:

```text
u16 frame_count
for each frame:
  u32 frame_end_offset_minus_one
  u16 width = 320
  u16 height = 170
  u16 image_format = 3
RLE frame streams
```

The RLE stream is the layout used by GCC's `RLE_Compress.dll`:

- 16-bit little-endian block length.
- If the high bit is clear, copy that many following RGB565 pixels.
- If the high bit is set, repeat the single following RGB565 pixel
  `length & 0x7fff` times.

## Clean apply sequence

The sequence that produced stable output on the tested card is:

```text
0xe7 enable LCD
0xf2 0x01 start upload
0xf1 upload header
payload pages
0xf2 0x02 finish upload
0xe1 clear metric overlay
0xf3 lock loop to the intended mode
0xe5 force intended mode
0xaa save
0xe5 force intended mode again
0xaa save again
```

The second mode command matters. During testing, the panel sometimes retained
the prior visual mode until a second explicit set-mode after save.

