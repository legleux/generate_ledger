from pathlib import Path
import zlib

z_art = Path("art.bin").read_bytes()
art = zlib.decompress(z_art)
print(art.decode(encoding='utf-8'))
