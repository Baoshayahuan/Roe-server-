# -*- coding: utf-8 -*-
"""Fix UnboundLocalError('bots') in the team branch: PULL_INFO (0x702f) crashed
before replying, so the client never received its squad and the connection died.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
text = HB.read_text(encoding='utf-8')

old = """                                        if code == 0x702f and team['body'] is None and getattr(args, 'coop', False):
                                            peers = [(u, n) for u, n in roster.values() if u]
                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]
                                            seen, unique = set(), []
                                            for member_uid, member_name in members:
                                                if member_uid in seen:
                                                    continue
                                                seen.add(member_uid)
                                                unique.append((member_uid, member_name))
                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2), nickname,
                                                                     members=unique[:3])
                                            capture.record('coop_pull_info', count=len(unique[:3]), **info)
                                        if code == 0x701d:
                                            bots = int(getattr(args, 'team_bots', 0) or 0)
                                        if bots:
                                            members = bot_members(uid, nickname, bots)
                                        elif getattr(args, 'coop', False):
                                            peers = [(u, n) for u, n in roster.values() if u and u != uid]
                                            members = [(uid, nickname)] + peers[:2]
                                        else:
                                            members = None
                                        team['body'] = team_body(uid, body, nickname, members=members)
                                        if bots:
                                            capture.record('team_bots', count=bots, members=[hex(u) for u, _ in members], **info)
"""

new = """                                        bots = int(getattr(args, 'team_bots', 0) or 0)
                                        if code == 0x701d:
                                            if bots:
                                                members = bot_members(uid, nickname, bots)
                                            elif getattr(args, 'coop', False):
                                                peers = [(u, n) for u, n in roster.values() if u and u != uid]
                                                members = [(uid, nickname)] + peers[:2]
                                            else:
                                                members = None
                                            team['body'] = team_body(uid, body, nickname, members=members)
                                            if bots:
                                                capture.record('team_bots', count=bots,
                                                               members=[hex(u) for u, _ in members], **info)
                                        elif team['body'] is None and getattr(args, 'coop', False):
                                            # PULL_INFO on a fresh connection: synthesize the squad.
                                            peers = [(u, n) for u, n in roster.values() if u]
                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]
                                            seen, unique = set(), []
                                            for member_uid, member_name in members:
                                                if member_uid in seen:
                                                    continue
                                                seen.add(member_uid)
                                                unique.append((member_uid, member_name))
                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),
                                                                     nickname, members=unique[:3])
                                            capture.record('coop_pull_info', count=len(unique[:3]), **info)
"""

if new in text:
    print('skip')
elif old not in text:
    raise SystemExit('anchor missing')
else:
    HB.write_text(text.replace(old, new, 1), encoding='utf-8')
    print('patched')

ast.parse(HB.read_text(encoding='utf-8'))
print('syntax ok')
