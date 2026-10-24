# -*- coding: utf-8 -*-
"""Scan decrypted lobby payloads for mode/map identifiers and lock-like flags."""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from roe_protocol_2022 import decrypt  # noqa: E402

key = (ROOT / 'private' / 'candidate-001.key').read_bytes()
src = (ROOT / 'search' / 'Ring-of-Elysium-Lobby-Emulator' / 'LobbyEmulator' / 'Logic' / 'LobbyPreData.cs').read_text(encoding='utf-8')
blobs = re.findall(r'"([0-9A-F]{32,})"', src)

targets = {16007: 'normal', 16010: 'iceland', 16023: 'training', 16024: 'training?'}
for index, blob in enumerate(blobs):
    try:
        plain = decrypt(bytes.fromhex(blob), key)
    except Exception:
        continue
    print(f'--- blob {index} {len(plain)}B')
    for value, name in targets.items():
        needle = struct.pack('>I', value)
        at = plain.find(needle)
        while at >= 0:
            print(f'   {name} {value} @ {at}: ...{plain[max(0, at-16):at+24].hex(" ")}')
            at = plain.find(needle, at + 1)
    # also look for small mode tables: sequences of 2..6 BE32 in range 16000-16100
    for at in range(0, len(plain) - 24, 4):
        values = struct.unpack_from('>6I', plain, at)
        if all(16000 <= v <= 16100 for v in values[:3]) and values[3] <= 8:
            print(f'   mode-table @{at}: {values}')
