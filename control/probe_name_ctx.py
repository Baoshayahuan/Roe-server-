# -*- coding: utf-8 -*-
"""Show the bytes around the hard-coded lobby nickname."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from roe_protocol_2022 import decrypt  # noqa: E402

key = (ROOT / 'private' / 'candidate-001.key').read_bytes()
src = (ROOT / 'search' / 'Ring-of-Elysium-Lobby-Emulator' / 'LobbyEmulator' / 'Logic' / 'LobbyPreData.cs').read_text(encoding='utf-8')
blobs = re.findall(r'"([0-9A-F]{32,})"', src)
plain = decrypt(bytes.fromhex(blobs[2]), key)
at = plain.find(b'BRING_BACK_ROE!!')
print('offset', at, 'len', len(plain), 'plain_len', len(plain))
lo = max(0, at - 48)
print('context hex:', plain[lo:at + 40].hex(' '))
print('before ascii:', plain[lo:at])
print('after  ascii:', plain[at + 16:at + 48])
# look for a length byte/word right before the string
for delta in (1, 2, 4):
    chunk = plain[at - delta:at]
    print('prev', delta, 'bytes:', chunk.hex(), int.from_bytes(chunk, 'little'), int.from_bytes(chunk, 'big'))
print('total occurrences:', plain.count(b'BRING_BACK_ROE!!'))
