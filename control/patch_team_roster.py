# -*- coding: utf-8 -*-
"""Spawn the two AI teammates as passive scene actors with matching UIDs."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WL = ROOT / 'tools' / 'windows_launch.py'
text = WL.read_text(encoding='utf-8')
changes = []


def patch(old, new, tag):
    global text
    if new in text:
        changes.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit('anchor missing: ' + tag)
    text = text.replace(old, new, 1)
    changes.append('patch ' + tag)


patch(
    "account_profile='default', winter_doors=False, winter_windows=False, cycle_scale=1, diagnostic_hazard=False, practice_targets=1):",
    "account_profile='default', winter_doors=False, winter_windows=False, cycle_scale=1, diagnostic_hazard=False, practice_targets=1, team_bots=0):",
    'signature')

patch(
    "    if practice_targets > 1:\n"
    "        points = json.loads((ROOT/'config/practice-target-points.json').read_text())\n"
    "        if points['map_id'] != 16010:\n"
    "            raise ValueError('PracticeTargets требует map16010')",
    "    if team_bots:\n"
    "        practice_targets = max(practice_targets, team_bots)\n"
    "    if practice_targets > 1:\n"
    "        points = json.loads((ROOT/'config/practice-target-points.json').read_text())\n"
    "        if points['map_id'] != 16010:\n"
    "            raise ValueError('PracticeTargets требует map16010')\n"
    "        if team_bots:\n"
    "            from team_bots_2022 import bot_points\n"
    "            points['targets'] = bot_points(team_bots, ROOT) + points['targets'][team_bots:]",
    'points')

text = text.replace("practice_targets=args.practice_targets)", "practice_targets=args.practice_targets,team_bots=args.team_bots)")
WL.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changes))
print('syntax ok')
