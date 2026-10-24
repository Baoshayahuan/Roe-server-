# -*- coding: utf-8 -*-
"""Enable peer trajectories + equipment replication in co-op."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WL = ROOT / 'tools' / 'windows_launch.py'
text = WL.read_text(encoding='utf-8')
old = "*(['--peer-avatar-config',str(configs['peer-avatar']),'--shared-ground-loot','--shared-peer-health'] if args.coop else []),"
new = "*(['--peer-avatar-config',str(configs['peer-avatar']),'--shared-ground-loot','--shared-peer-health','--peer-avatar-trajectories','--peer-equipment'] if args.coop else []),"
if new in text:
    print('skip')
elif old in text:
    WL.write_text(text.replace(old, new, 1), encoding='utf-8')
    print('patched')
else:
    raise SystemExit('anchor missing')

ast.parse(WL.read_text(encoding='utf-8'))
print('syntax ok')
