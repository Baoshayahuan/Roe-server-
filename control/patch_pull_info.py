# -*- coding: utf-8 -*-
"""The client asks for team info (0x702f) during the match; the proxy rejected it
("UID mismatch" / "team not created"), so the squad never appeared. In co-op we
now answer PULL_INFO with a synthesized squad from the live roster.
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


sub("                                    if not team['uid'] or uid != team['uid']:\n"
    "                                        reason = 'UID не совпал с ENTER_GAME_RSP'",
    "                                    if (not team['uid'] or uid != team['uid']) and not getattr(args, 'coop', False):\n"
    "                                        reason = 'UID не совпал с ENTER_GAME_RSP'",
    'uid-check')

sub("                                    elif code == 0x702f and team['body'] is None:\n"
    "                                        reason = 'Команда ещё не создана; PULL_INFO до CREATE пропущен'",
    "                                    elif code == 0x702f and team['body'] is None and not getattr(args, 'coop', False):\n"
    "                                        reason = 'Команда ещё не создана; PULL_INFO до CREATE пропущен'",
    'pullinfo-check')

sub("                                        if code == 0x701d:\n"
    "                                            bots = int(getattr(args, 'team_bots', 0) or 0)",
    "                                        if code == 0x702f and team['body'] is None and getattr(args, 'coop', False):\n"
    "                                            peers = [(u, n) for u, n in roster.values() if u]\n"
    "                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]\n"
    "                                            seen, unique = set(), []\n"
    "                                            for member_uid, member_name in members:\n"
    "                                                if member_uid in seen:\n"
    "                                                    continue\n"
    "                                                seen.add(member_uid)\n"
    "                                                unique.append((member_uid, member_name))\n"
    "                                            team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2), nickname,\n"
    "                                                                     members=unique[:3])\n"
    "                                            capture.record('coop_pull_info', count=len(unique[:3]), **info)\n"
    "                                        if code == 0x701d:\n"
    "                                            bots = int(getattr(args, 'team_bots', 0) or 0)",
    'pullinfo-build')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
