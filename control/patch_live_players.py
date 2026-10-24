# -*- coding: utf-8 -*-
"""Panel: list players of the current run and allow targeting one with live actions."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'control' / 'app.py'
text = APP.read_text(encoding='utf-8')
changed = []

PLAYERS = '''_PLAYERS_CACHE = {}


def live_players(run):
    """Online players of the current run, parsed from the lobby proxy log."""
    path = Path(run) / 'proxy.log'
    if not path.is_file():
        return []
    stat = path.stat()
    key = (str(path), stat.st_mtime, stat.st_size)
    cached = _PLAYERS_CACHE.get('value')
    if cached and cached[0] == key:
        return cached[1]
    online, assigned = {}, {}
    try:
        with path.open(encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if '"account_assigned"' in line:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    rec = dict(uid=row.get('actor_uid'), name=row.get('profile'),
                               remote=row.get('remote'), connection=row.get('connection'))
                    if rec['uid']:
                        assigned[row.get('connection')] = rec
                        online[row.get('connection')] = rec
                elif '"kind": "disconnect"' in line:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    online.pop(row.get('connection'), None)
    except OSError:
        return []
    rows = list((online or assigned).values())
    _PLAYERS_CACHE['value'] = (key, rows)
    return rows


def live_results(run):'''


def sub(old, new, tag):
    global text
    if new in text:
        changed.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit('anchor missing: ' + tag)
    text = text.replace(old, new, 1)
    changed.append('patch ' + tag)


sub('def live_results(run):', PLAYERS, 'players')
sub("            out['results'] = live_results(run)",
    "            out['results'] = live_results(run)\n            out['players'] = live_players(run)",
    'status')
sub("        if body.get('npc_uid'):\n            row['npc_uid'] = str(body['npc_uid'])",
    "        if body.get('npc_uid'):\n            row['npc_uid'] = str(body['npc_uid'])\n"
    "        if body.get('recipient'):\n            row['recipient_actor_uid'] = str(body['recipient'])",
    'recipient')

APP.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
