"""Linux I2C transport."""

from __future__ import annotations

import ctypes
import fcntl
import os
import time

from .protocol import Target

I2C_RDWR = 0x0707
I2C_M_RD = 0x0001


class I2CMsg(ctypes.Structure):
    _fields_ = [
        ("addr", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("len", ctypes.c_uint16),
        ("buf", ctypes.POINTER(ctypes.c_uint8)),
    ]


class I2CRdwrIoctlData(ctypes.Structure):
    _fields_ = [
        ("msgs", ctypes.POINTER(I2CMsg)),
        ("nmsgs", ctypes.c_uint32),
    ]


class I2CTransport:
    """Small wrapper around Linux's I2C_RDWR ioctl."""

    def __init__(self, target: Target, retries: int = 8, retry_delay: float = 0.25) -> None:
        self.target = target
        self.retries = retries
        self.retry_delay = retry_delay

    def write(self, payload: bytes) -> None:
        for attempt in range(self.retries):
            try:
                self._rdwr([(self.target.addr, 0, payload)])
                return
            except OSError:
                if attempt + 1 >= self.retries:
                    raise
                time.sleep(self.retry_delay)

    def write_read(self, payload: bytes, read_len: int) -> bytes:
        for attempt in range(self.retries):
            try:
                return self._rdwr(
                    [
                        (self.target.addr, 0, payload),
                        (self.target.addr, I2C_M_RD, bytes(read_len)),
                    ]
                )[1]
            except OSError:
                if attempt + 1 >= self.retries:
                    raise
                time.sleep(self.retry_delay)
        raise RuntimeError("unreachable")

    def _rdwr(self, messages: list[tuple[int, int, bytes]]) -> list[bytes]:
        fd = os.open(self.target.path, os.O_RDWR)
        buffers = []
        try:
            msg_array = (I2CMsg * len(messages))()
            for index, (addr, flags, payload) in enumerate(messages):
                buf = (ctypes.c_uint8 * len(payload))(*payload)
                buffers.append(buf)
                msg_array[index] = I2CMsg(addr, flags, len(payload), buf)
            ioctl_data = I2CRdwrIoctlData(msg_array, len(messages))
            fcntl.ioctl(fd, I2C_RDWR, ioctl_data)
            return [bytes(buf) for buf in buffers]
        finally:
            os.close(fd)
