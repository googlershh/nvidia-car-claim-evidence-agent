"""Extract plain text from an HWP 5.x file using only the standard library.

HWP 5 is an OLE compound file; body text lives in BodyText/SectionN streams
as (optionally deflate-compressed) records. Paragraph text is in
HWPTAG_PARA_TEXT records (UTF-16LE with embedded control characters).
Table cells are paragraphs too, so they come out one cell per line.

Usage:
    python scripts/hwp_text.py <file.hwp> [out.txt]
"""

from __future__ import annotations

import re
import struct
import sys
import zlib
from pathlib import Path

FREESECT, ENDOFCHAIN = 0xFFFFFFFF, 0xFFFFFFFE
HWPTAG_PARA_TEXT = 16 + 51
# Control chars that occupy 8 WCHARs (inline/extended controls); others occupy 1.
WIDE_CONTROLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


class OleFile:
    def __init__(self, data: bytes):
        self.data = data
        hdr = data[:512]
        if hdr[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
            raise ValueError("not an OLE compound file")
        self.sector_size = 1 << struct.unpack_from("<H", hdr, 30)[0]
        self.mini_size = 1 << struct.unpack_from("<H", hdr, 32)[0]
        dir_start, = struct.unpack_from("<I", hdr, 48)
        self.mini_cutoff, mini_fat_start, _, difat_start, n_difat = struct.unpack_from("<5I", hdr, 56)

        fat_sectors = [s for s in struct.unpack_from("<109I", hdr, 76) if s not in (FREESECT, ENDOFCHAIN)]
        per = self.sector_size // 4
        s = difat_start
        for _ in range(n_difat):
            vals = struct.unpack_from(f"<{per}I", self._sector(s))
            fat_sectors += [v for v in vals[:-1] if v not in (FREESECT, ENDOFCHAIN)]
            s = vals[-1]
        self.fat = [v for fs in fat_sectors for v in struct.unpack_from(f"<{per}I", self._sector(fs))]

        dir_bytes = self._read_chain(dir_start)
        self.entries = []
        for off in range(0, len(dir_bytes), 128):
            e = dir_bytes[off:off + 128]
            name_len, = struct.unpack_from("<H", e, 64)
            name = e[:max(name_len - 2, 0)].decode("utf-16le")
            etype = e[66]
            start, size = struct.unpack_from("<IQ", e, 116)
            self.entries.append((name, etype, start, size))
        root = self.entries[0]
        self.mini_stream = self._read_chain(root[2])[:root[3]]
        self.mini_fat = list(struct.unpack(f"<{len(b) // 4}I", b)) if (b := self._read_chain(mini_fat_start)) else []

    def _sector(self, idx: int) -> bytes:
        off = 512 + idx * self.sector_size
        return self.data[off:off + self.sector_size]

    def _read_chain(self, start: int) -> bytes:
        out, s = [], start
        while s not in (ENDOFCHAIN, FREESECT) and s < len(self.fat) + 1:
            out.append(self._sector(s))
            s = self.fat[s]
        return b"".join(out)

    def stream(self, name: str) -> bytes:
        for ename, etype, start, size in self.entries:
            if ename == name and etype == 2:
                if size < self.mini_cutoff:
                    out, s = [], start
                    while s not in (ENDOFCHAIN, FREESECT):
                        out.append(self.mini_stream[s * self.mini_size:(s + 1) * self.mini_size])
                        s = self.mini_fat[s]
                    return b"".join(out)[:size]
                return self._read_chain(start)[:size]
        raise KeyError(name)

    def names(self) -> list[str]:
        return [e[0] for e in self.entries if e[1] == 2]


def para_text(raw: bytes) -> str:
    chars = struct.unpack(f"<{len(raw) // 2}H", raw[:len(raw) // 2 * 2])
    out, i = [], 0
    while i < len(chars):
        c = chars[i]
        if c < 32:
            if c in WIDE_CONTROLS:
                i += 8
                if c == 9:
                    out.append("\t")
                continue
            if c in (10, 13):
                out.append("\n")
            i += 1
            continue
        out.append(chr(c))
        i += 1
    return "".join(out)


def hwp_to_text(path: Path) -> str:
    ole = OleFile(path.read_bytes())
    compressed = bool(struct.unpack_from("<I", ole.stream("FileHeader"), 36)[0] & 1)
    sections = sorted((n for n in ole.names() if re.fullmatch(r"Section\d+", n)), key=lambda n: int(n[7:]))
    lines = []
    for sec in sections:
        data = ole.stream(sec)
        if compressed:
            data = zlib.decompress(data, -15)
        pos = 0
        while pos + 4 <= len(data):
            header, = struct.unpack_from("<I", data, pos)
            pos += 4
            tag, size = header & 0x3FF, header >> 20
            if size == 0xFFF:
                size, = struct.unpack_from("<I", data, pos)
                pos += 4
            if tag == HWPTAG_PARA_TEXT:
                lines.append(para_text(data[pos:pos + size]).rstrip())
            pos += size
    return "\n".join(lines)


if __name__ == "__main__":
    src = Path(sys.argv[1])
    text = hwp_to_text(src)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
