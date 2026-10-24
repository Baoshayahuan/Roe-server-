# -*- coding: utf-8 -*-
"""Panel: don't report an older run/ready state as the current server."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'control' / 'app.py'
text = APP.read_text(encoding='utf-8')
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


sub("        dirs = [d for d in RUNS.iterdir() if d.is_dir()]",
    "        since = (self.started or 0) - 5\n"
    "        dirs = [d for d in RUNS.iterdir() if d.is_dir() and d.stat().st_mtime >= since]",
    'since')

sub("            info['events'] = count_events(run)",
    "            info['events'] = count_events(run)\n"
    "            if not alive:\n"
    "                info['ready'] = {key: False for key in info['ready']}",
    'ready')

APP.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
