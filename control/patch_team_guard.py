# -*- coding: utf-8 -*-
"""Never reply with a None team body (that crashed the lobby handler twice)."""
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


# 1. any PULL_INFO/CREATE without a body gets a synthesized one when co-op is on
sub("                                        elif (getattr(args, 'coop', False)\n"
    "                                              and getattr(args, 'coop_team_sync', False)):\n"
    "                                            if team_template['body'] is not None:",
    "                                        elif (getattr(args, 'coop', False)\n"
    "                                              and getattr(args, 'coop_team_sync', False)):\n"
    "                                            if team['body'] is None and team_template['body'] is None:\n"
    "                                                members = coop_squad(uid, nickname)\n"
    "                                                team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),\n"
    "                                                                         nickname, members=members)\n"
    "                                                capture.record('coop_pull_info', count=len(members), **info)\n"
    "                                            if team_template['body'] is not None:",
    'ensure-body')

# 2. guard the reply: log instead of crashing
sub("                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff\n"
    "                                        reply_code = 0x701e if code == 0x701d else 0x7030\n"
    "                                        response = server_message(reply_code, team['body'], stamp, key)",
    "                                        if team['body'] is None:\n"
    "                                            capture.record('team_empty', code=hex(code),\n"
    "                                                           coop=getattr(args, 'coop', False),\n"
    "                                                           team_sync=getattr(args, 'coop_team_sync', False), **info)\n"
    "                                            status()\n"
    "                                            continue\n"
    "                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff\n"
    "                                        reply_code = 0x701e if code == 0x701d else 0x7030\n"
    "                                        response = server_message(reply_code, team['body'], stamp, key)",
    'guard')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
