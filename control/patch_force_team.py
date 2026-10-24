# -*- coding: utf-8 -*-
"""Force a 3-man squad in solo training + keep the bots within arm's reach."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
BOTS = ROOT / 'server' / 'directory' / 'team_bots_2022.py'
changes = []


def patch(path, old, new, tag):
    text = path.read_text(encoding='utf-8')
    if new in text:
        changes.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit(f'anchor missing: {tag} in {path.name}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    changes.append('patch ' + tag)


# bots right next to the default training spawn (365030, 543960)
patch(BOTS,
      "BOT_POSITIONS = (\n    (365150, 544060, 259111),\n    (364900, 544060, 259111),\n)",
      "BOT_POSITIONS = (\n    (365150, 543960, 259111),\n    (364910, 543960, 259111),\n)",
      'bots.positions')

# solo training request -> synthesise the squad and push it to the client
patch(HB,
      "                                        if code == 0x6e29:\n"
      "                                            match_type = struct.unpack_from('>I', body)[0]",
      "                                        bots = int(getattr(args, 'team_bots', 0) or 0)\n"
      "                                        if (bots and code == 0x6e29 and team['body'] is None\n"
      "                                                and struct.unpack_from('>I', body, 16)[0] == 16023):\n"
      "                                            create_body = struct.pack('>4I', 1, 16023, 1, 2)\n"
      "                                            team['body'] = team_body(uid, create_body, nickname,\n"
      "                                                                     members=bot_members(uid, nickname, bots))\n"
      "                                            stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff\n"
      "                                            pushed = server_message(0x701e, team['body'], stamp, key)\n"
      "                                            async with outgoing:\n"
      "                                                writer.write(pushed)\n"
      "                                                capture.record('data', pushed, direction='server_to_client', origin='forced_team', **info)\n"
      "                                                await writer.drain()\n"
      "                                            capture.record('forced_team', count=bots + 1, members=[hex(u) for u, _ in bot_members(uid, nickname, bots)], **info)\n"
      "                                        if code == 0x6e29:\n"
      "                                            match_type = struct.unpack_from('>I', body)[0]",
      'hb.force')

for path in (HB, BOTS):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
