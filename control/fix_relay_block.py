# -*- coding: utf-8 -*-
"""Rewrite the mangled PULL_INFO block: raw relay only (no member cloning)."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
lines = HB.read_text(encoding='utf-8').splitlines()

start = None
for i, line in enumerate(lines):
    if line.strip() == "if team_template['body'] is not None:" and start is None:
        start = i
        break
if start is None:
    raise SystemExit('start anchor missing')

end = start
while end + 1 < len(lines) and (lines[end + 1].startswith(' ' * 48) or not lines[end + 1].strip()):
    end += 1

block = [
    "                                            if team_template['body'] is not None:",
    "                                                # relay the creator's own body verbatim (no cloning)",
    "                                                team['body'] = team_template['body']",
    "                                                capture.record('coop_team_raw', source='template', **info)",
    "                                            elif team['body'] is None:",
    "                                                members = coop_squad(uid, nickname)",
    "                                                team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),",
    "                                                                         nickname, members=members)",
    "                                                capture.record('coop_pull_info', count=len(members), **info)",
]
lines[start:end + 1] = block
HB.write_text('\n'.join(lines) + '\n', encoding='utf-8')
ast.parse(HB.read_text(encoding='utf-8'))
print('rewrote lines', start + 1, '..', end + 1)
print('syntax ok')
