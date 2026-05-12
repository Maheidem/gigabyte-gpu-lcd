# Hardware Notes

## Validated card

```text
GPU: Gigabyte AORUS GeForce RTX 5090 MASTER ICE 32G
PCI device: 10de:2b85
PCI subsystem: 1458:4199
GCC database key: 10DE_1458_4199_2B85
GCC UiId: 21, parsed by GCC as hex 0x21 / decimal 33
LCD I2C bus: /dev/i2c-3
LCD I2C address: 0x61
Firmware response: d6 14 01 02
Parsed firmware: F1.4
```

## RGB vs LCD

The GPU RGB zones and the LCD are separate control paths.

OpenRGB exposed the GPU RGB controller on `/dev/i2c-3` at address `0x75`. That
path controlled RGB lighting, not the LCD. The LCD was controlled by direct I2C
commands to address `0x61`.

Case fan LEDs attached to the motherboard are also separate from the GPU LCD.
They should be treated as motherboard/OpenRGB RGB devices, not as part of this
LCD protocol.

## Vendor source used for mapping

The protocol was recovered from Gigabyte Control Center package
`GCC_26.03.31.01.zip`, especially VGA module `GBT_VGA_26.03.10.01.exe`.

Useful managed components found in that package:

- `ucVga.Api.GvLcdApi`: old LCD protocol used by this card.
- `ucVga.Api.GvLcdExApi`: newer LCD protocol that did not answer here.
- `ucVga.Api.I2CApi`: wrapper around `GvWriteI2C` and `GvReadI2C`.
- `ucVga.Common.ImageMaker`: image/GIF container creation.
- `RLE_Compress.dll`: animation RLE stream format.

Those vendor files are not redistributed in this repo.

## Discovery notes

The newer probe path failed:

```text
/dev/i2c-3 addr 0x76 GvLcdEx FW: Input/output error
```

The old path worked:

```text
/dev/i2c-3 addr 0x61 GvLcd old FW: d6 14 01 02
```

This package defaults to the old path:

```text
--bus 3 --addr 0x61 --device-id 0x21
```

Override those values only after probing your own hardware.

