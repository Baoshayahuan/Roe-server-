# -*- coding: utf-8 -*-
"""Relay the client's own team body (plus one cloned member) instead of inventing one."""
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


sub("from roe_team_2022 import client_message, server_message, team_body",
    "from roe_team_2022 import client_message, server_message, team_body, with_member",
    'import')

sub("    roster = {}  # connection -> (uid, name); shared by all lobby connections",
    "    roster = {}  # connection -> (uid, name); shared by all lobby connections\n"
    "    team_template = {'body': None}  # last real CREATE body from a client",
    'template-var')

sub("                                            team['body'] = team_body(uid, body, nickname, members=members)",
    "                                            team['body'] = team_body(uid, body, nickname, members=members)\n"
    "                                            if members is None or members == []:\n"
    "                                                team_template['body'] = team['body']\n"
    "                                            elif getattr(args, 'coop_team_sync', False):\n"
    "                                                team_template['body'] = team['body']",
    'store-template')

sub("                                        elif (team['body'] is None and getattr(args, 'coop', False)\n"
    "                                              and getattr(args, 'coop_team_sync', False)):\n"
    "                                            # PULL_INFO on a fresh connection: synthesize the squad.\n"
    "                                            members = coop_squad(uid, nickname)\n"
    "                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),\n"
    "                                                                     nickname, members=members)\n"
    "                                            capture.record('coop_pull_info', count=len(members), **info)",
    "                                        elif (getattr(args, 'coop', False)\n"
    "                                              and getattr(args, 'coop_team_sync', False)):\n"
    "                                            if team_template['body'] is not None:\n"
    "                                                # relay the client's own team, plus one cloned member\n"
    "                                                team['body'] = with_member(team_template['body'], uid, nickname)\n"
    "                                                capture.record('coop_team_relay', count=2, **info)\n"
    "                                            elif team['body'] is None:\n"
    "                                                members = coop_squad(uid, nickname)\n"
    "                                                team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),\n"
    "                                                                         nickname, members=members)\n"
    "                                                capture.record('coop_pull_info', count=len(members), **info)",
    'relay')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
