# -*- coding: utf-8 -*-
"""Co-op matchmaking: put every connected player into one squad and push it to all.

The client only builds a squad from its own CREATE/TEAM responses, so when two
players queue separately neither sees the other.  At match request time the proxy
now composes one team body from the live roster (self first) and broadcasts it to
every lobby connection before answering the match request.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
text = HB.read_text(encoding='utf-8')
changes = []

BLOCK = '''                                        if getattr(args, 'coop', False) and code == 0x6e29:
                                            peers = [(u, n) for u, n in roster.values() if u]
                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]
                                            seen, unique = set(), []
                                            for member_uid, member_name in members:
                                                if member_uid in seen:
                                                    continue
                                                seen.add(member_uid)
                                                unique.append((member_uid, member_name))
                                            map_id = struct.unpack_from('>I', body, 16)[0]
                                            create_body = struct.pack('>4I', 1, map_id, 1, 2)
                                            team['body'] = team_body(uid, create_body, nickname, members=unique[:3])
                                            if clock['stamp'] is not None:
                                                stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                                payload = team['body']
                                                for other_id, other in list(sockets.items()):
                                                    if other.is_closing():
                                                        continue
                                                    other.write(server_message(0x701e, payload, stamp, key))
                                                await asyncio.gather(*[w.drain() for w in list(sockets.values()) if not w.is_closing()], return_exceptions=True)
                                            capture.record('coop_team_push', count=len(unique[:3]),
                                                           members=[hex(u) for u, _ in unique[:3]], **info)
'''

anchor = "                                        if code == 0x6e29:\n                                            match_type = struct.unpack_from('>I', body)[0]"
if BLOCK.strip() in text:
    changes.append('skip coop.match')
elif anchor not in text:
    raise SystemExit('anchor missing')
else:
    text = text.replace(anchor, BLOCK + anchor, 1)
    changes.append('patch coop.match')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changes))
print('syntax ok')
