"""Minimal Modbus TCP client (Milestone G7). No third-party dependency.

Only what the farm adapter needs: read holding registers (FC 3), write one register (FC 6)
and write many registers (FC 16). Every request carries the MBAP header:
transaction id, protocol id (0), length, unit id; then the PDU.
"""

from __future__ import annotations

import asyncio
import struct


class ModbusError(Exception):
    pass


class ModbusTcpClient:
    def __init__(self, host: str, port: int = 502, unit: int = 1, timeout: float = 3.0):
        self.host, self.port, self.unit, self.timeout = host, port, unit, timeout
        self._r: asyncio.StreamReader | None = None
        self._w: asyncio.StreamWriter | None = None
        self._tid = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._r, self._w = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), self.timeout
        )

    async def close(self) -> None:
        if self._w is not None:
            self._w.close()
            try:
                await self._w.wait_closed()
            except (ConnectionError, OSError):
                pass
        self._r = self._w = None

    @property
    def connected(self) -> bool:
        return self._w is not None and not self._w.is_closing()

    async def _call(self, pdu: bytes) -> bytes:
        if not self.connected:
            await self.connect()
        async with self._lock:
            self._tid = (self._tid + 1) & 0xFFFF
            try:
                self._w.write(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self.unit) + pdu)
                await self._w.drain()
                head = await asyncio.wait_for(self._r.readexactly(7), self.timeout)
                tid, _pid, length, _unit = struct.unpack(">HHHB", head)
                body = await asyncio.wait_for(self._r.readexactly(length - 1), self.timeout)
                if tid != self._tid:
                    raise ModbusError(f"transaction mismatch {tid} != {self._tid}")
            except BaseException:
                # a late or lost reply leaves the stream out of step: drop it, reconnect next call
                await self.close()
                raise
        if body[0] & 0x80:
            raise ModbusError(f"exception code {body[1]} for function {body[0] & 0x7F}")
        return body

    async def read_holding(self, address: int, count: int) -> list[int]:
        body = await self._call(struct.pack(">BHH", 3, address, count))
        n = body[1] // 2
        return list(struct.unpack(f">{n}H", body[2 : 2 + 2 * n]))

    async def write_register(self, address: int, value: int) -> None:
        await self._call(struct.pack(">BHH", 6, address, value & 0xFFFF))

    async def write_registers(self, address: int, values: list[int]) -> None:
        data = b"".join(struct.pack(">H", v & 0xFFFF) for v in values)
        await self._call(struct.pack(">BHHB", 16, address, len(values), len(data)) + data)


class ModbusTcpServer:
    """Tiny register-bank server for tests and bench checks (FC 3, 6, 16)."""

    def __init__(self, size: int = 1000):
        self.regs = [0] * size
        self.on_write = None  # optional callback(address, values) after each write
        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.StreamWriter] = set()

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        self._server = await asyncio.start_server(self._handle, host, port)
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            for w in list(self._clients):
                w.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        self._clients.add(w)
        try:
            while True:
                head = await r.readexactly(7)
                tid, pid, length, unit = struct.unpack(">HHHB", head)
                pdu = await r.readexactly(length - 1)
                fc = pdu[0]
                if fc == 3:
                    addr, count = struct.unpack(">HH", pdu[1:5])
                    vals = self.regs[addr : addr + count]
                    out = struct.pack(">BB", 3, 2 * count) + b"".join(
                        struct.pack(">H", v) for v in vals
                    )
                elif fc == 6:
                    addr, val = struct.unpack(">HH", pdu[1:5])
                    self.regs[addr] = val
                    out = pdu[:5]
                    if self.on_write:
                        self.on_write(addr, [val])
                elif fc == 16:
                    addr, count, _n = struct.unpack(">HHB", pdu[1:6])
                    vals = list(struct.unpack(f">{count}H", pdu[6 : 6 + 2 * count]))
                    self.regs[addr : addr + count] = vals
                    out = struct.pack(">BHH", 16, addr, count)
                    if self.on_write:
                        self.on_write(addr, vals)
                else:
                    out = struct.pack(">BB", fc | 0x80, 1)
                w.write(struct.pack(">HHHB", tid, pid, len(out) + 1, unit) + out)
                await w.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._clients.discard(w)
            w.close()
