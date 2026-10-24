# -*- coding: utf-8 -*-
"""Co-op fixes:
1. allow live admin actions while shared loot is on (per-connection state)
2. push the created squad to the other connected player so both see 2 members
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
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


patch(EP,
      "                                            if code is None:\n"
      "                                                if self.shared_loot:\n"
      "                                                    packets,event = [],dict(action=payload['action'],accepted=False,reason='solo_action_only')\n"
      "                                                else:\n"
      "                                                    try:\n"
      "                                                        packets,event = apply_state_action(state,payload,self.death_reserved_indexes(state))\n"
      "                                                    except ValueError as error:\n"
      "                                                        packets,event = [],dict(action=payload['action'],accepted=False,reason=str(error))",
      "                                            if code is None:\n"
      "                                                try:\n"
      "                                                    packets,event = apply_state_action(state,payload,self.death_reserved_indexes(state))\n"
      "                                                except ValueError as error:\n"
      "                                                    packets,event = [],dict(action=payload['action'],accepted=False,reason=str(error))",
      'ep.allow-actions')

patch(HB,
      "    roster = {}  # connection -> (uid, name); shared by all lobby connections",
      "    roster = {}  # connection -> (uid, name); shared by all lobby connections\n"
      "    sockets = {}  # connection -> StreamWriter, for room broadcasts",
      'hb.sockets')

patch(HB,
      "        capture.record('connect', **info, remote=writer.get_extra_info('peername'))",
      "        sockets[connection] = writer\n"
      "        capture.record('connect', **info, remote=writer.get_extra_info('peername'))",
      'hb.socket-register')

patch(HB,
      "                                        totals['team_replies'] += 1",
      "                                        if getattr(args, 'coop', False):\n"
      "                                            for other_id, other in list(sockets.items()):\n"
      "                                                if other_id == connection or other.is_closing():\n"
      "                                                    continue\n"
      "                                                other.write(server_message(reply_code, team['body'], stamp, key))\n"
      "                                                capture.record('data', b'', direction='server_to_client', origin='team_broadcast', connection=other_id)\n"
      "                                            await asyncio.gather(*[w.drain() for w in list(sockets.values()) if not w.is_closing()], return_exceptions=True)\n"
      "                                        totals['team_replies'] += 1",
      'hb.team-broadcast')

for path in (EP, HB):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
