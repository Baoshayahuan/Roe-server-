# -*- coding: utf-8 -*-
"""Minimal friend protocol probe: answer 0x7021 (list) and 0x702d (search).

The client hangs on "searching friends" because nothing answers these.  We reply
with a minimal (result=0, count=0) body; if the dialog stops hanging we know the
framing is right and can grow the payload from there.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
text = HB.read_text(encoding='utf-8')
changed = []


def sub(old, new, tag):
    global text
    if new in text:
        changed.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit('anchor missing: ' + tag)
    text = text.replace(old, new, 1)
    changed.append('patch ' + tag)


sub("                            if match_enabled:",
    "                            if getattr(args, 'coop', False):\n"
    "                                message = client_message(frame, key)\n"
    "                                if message and message[0] in (0x7021, 0x702d):\n"
    "                                    fcode, fuid, fbody = message\n"
    "                                    if enabled['server_to_client'] and clock['stamp'] is not None:\n"
    "                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff\n"
    "                                        reply = 0x7022 if fcode == 0x7021 else 0x702e\n"
    "                                        payload = struct.pack('>II', 0, 0)\n"
    "                                        response = server_message(reply, payload, stamp, key)\n"
    "                                        async with outgoing:\n"
    "                                            writer.write(response)\n"
    "                                            capture.record('data', response, direction='server_to_client',\n"
    "                                                           origin='friend_probe', **info)\n"
    "                                            await writer.drain()\n"
    "                                        capture.record('friend_probe', code=hex(fcode), reply=hex(reply),\n"
    "                                                       request_length=len(fbody), **info)\n"
    "                            if match_enabled:",
    'friend-probe')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
