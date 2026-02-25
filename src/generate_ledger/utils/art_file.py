import zlib
from pathlib import Path

z_art = Path("art.bin").read_bytes()
art = zlib.decompress(z_art)
print(art.decode(encoding='utf-8'))
