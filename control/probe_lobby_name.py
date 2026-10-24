# -*- coding: utf-8 -*-
"""Decrypt the lobby pre-data blobs and look for the displayed nickname."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from roe_protocol_2022 import decrypt  # noqa: E402

key = (ROOT / 'private' / 'candidate-001.key').read_bytes()
src = (ROOT / 'search' / 'Ring-of-Elysium-Lobby-Emulator' / 'LobbyEmulator' / 'Logic' / 'LobbyPreData.cs').read_text(encoding='utf-8')
blobs = re.findall(r'"([0-9A-F]{32,})"', src)
print('blobs:', len(blobs))

def strings(buf, minimum=4):
    out = []
    # utf-16-le
    for odd in (0, 1):
        chunk = buf[odd:]
        cur = bytearray()
        for i in range(0, len(chunk) - 1, 2):
            lo, hi = chunk[i], chunk[i + 1]
            if hi == 0 and 32 <= lo < 127:
                cur.append(lo)
            else:
                if len(cur) >= minimum:
                    out.append(('utf16', bytes(cur).decode('ascii')))
                cur.clear()
        if len(cur) >= minimum:
            out.append(('utf16', bytes(cur).decode('ascii')))
    # ascii
    cur = bytearray()
    for b in buf:
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= minimum:
                out.append(('ascii', bytes(cur).decode('ascii')))
            cur.clear()
    if len(cur) >= minimum:
        out.append(('ascii', bytes(cur).decode('ascii')))
    return out

for index, blob in enumerate(blobs):
    raw = bytes.fromhex(blob)
    try:
        plain = decrypt(raw, key)
    except Exception as exc:  # noqa: BLE001
        print(f'--- blob {index}: {len(raw)}B decrypt failed: {exc}')
        continue
    hits = [s for kind, s in strings(plain, 4)]
    interesting = [s for s in hits if any(t in s.upper() for t in ('BRING', 'ROE', 'PLAYER', 'GUEST', 'ELYSIUM'))]
    print(f'--- blob {index}: {len(raw)}B -> {len(plain)}B, strings={len(hits)}, interesting={interesting[:12]}')
    if index == 0:
        for kind, s in strings(plain, 5)[:40]:
            print('   ', kind, repr(s[:80]))

