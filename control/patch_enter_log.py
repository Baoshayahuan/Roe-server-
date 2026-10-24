# -*- coding: utf-8 -*-
"""Log the raw ENTER_ROOM request so two players' payloads can be compared."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
lines = EP.read_text(encoding='utf-8').splitlines(keepends=True)
anchor = "                                room=decode_enter_room_request(message.payload)\n"
insert = ("                                self.capture.record('enter_room_payload',\n"
          "                                                    payload_hex=message.payload.hex(),\n"
          "                                                    length=len(message.payload), remote=remote)\n")
if insert in ''.join(lines):
    print('skip')
else:
    index = None
    for i, line in enumerate(lines):
        if line == anchor:
            index = i
            break
    if index is None:
        raise SystemExit('anchor missing')
    lines.insert(index + 1, insert)
    EP.write_text(''.join(lines), encoding='utf-8')
    print('patched')

ast.parse(EP.read_text(encoding='utf-8'))
print('syntax ok')
