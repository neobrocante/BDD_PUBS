"""Crée les images de test (PNG unis, sans dépendance) dans le dossier donné."""
import os
import struct
import sys
import zlib


def png(path, w, h, color):
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    png(os.path.join(d, "image_bleue.png"), 600, 800, (40, 90, 160))
    png(os.path.join(d, "image_rouge.png"), 500, 700, (200, 60, 40))
