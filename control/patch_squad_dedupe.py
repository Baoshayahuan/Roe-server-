# -*- coding: utf-8 -*-
"""Team roster cleanup + dedupe (the squad showed the same player twice)."""
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


# 1. helper: one squad, deduped by account UID, max 2 in co-op
sub("    by_ip = {}   # remote ip -> account name (sticky across reconnects)",
    "    by_ip = {}   # remote ip -> account name (sticky across reconnects)\n"
    "\n"
    "    def coop_squad(self_uid, self_name):\n"
    "        members, seen = [(self_uid, self_name)], {self_uid}\n"
    "        for member_uid, member_name in roster.values():\n"
    "            if member_uid and member_uid not in seen:\n"
    "                seen.add(member_uid)\n"
    "                members.append((member_uid, member_name))\n"
    "        return members[:2]",
    'helper')

# 2. use it for CREATE and PULL_INFO
sub("                                            elif getattr(args, 'coop', False):\n"
    "                                                peers = [(u, n) for u, n in roster.values() if u and u != uid]\n"
    "                                                members = [(uid, nickname)] + peers[:2]",
    "                                            elif getattr(args, 'coop', False):\n"
    "                                                members = coop_squad(uid, nickname)",
    'create')

sub("                                            peers = [(u, n) for u, n in roster.values() if u]\n"
    "                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]\n"
    "                                            seen, unique = set(), []\n"
    "                                            for member_uid, member_name in members:\n"
    "                                                if member_uid in seen:\n"
    "                                                    continue\n"
    "                                                seen.add(member_uid)\n"
    "                                                unique.append((member_uid, member_name))\n"
    "                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),\n"
    "                                                                     nickname, members=unique[:3])\n"
    "                                            capture.record('coop_pull_info', count=len(unique[:3]), **info)",
    "                                            members = coop_squad(uid, nickname)\n"
    "                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),\n"
    "                                                                     nickname, members=members)\n"
    "                                            capture.record('coop_pull_info', count=len(members), **info)",
    'pullinfo')

# 3. cleanup stale roster/socket entries when a connection ends
sub("        finally:\n"
    "            for pump_task in pumps:\n"
    "                pump_task.cancel()",
    "        finally:\n"
    "            roster.pop(connection, None)\n"
    "            sockets.pop(connection, None)\n"
    "            for pump_task in pumps:\n"
    "                pump_task.cancel()",
    'cleanup')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
