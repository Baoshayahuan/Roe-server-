"""Normalize the indentation of the --host argument added to the endpoint CLI."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
lines = p.read_text(encoding='utf-8').splitlines()
for i, line in enumerate(lines):
    if "p.add_argument('--host',default='127.0.0.1')" in line:
        lines[i] = "    p.add_argument('--host',default='127.0.0.1')"
p.write_text('\n'.join(lines) + '\n', encoding='utf-8')

for f in ['tools/heartbeat_probe_2022.py', 'server/directory/game_endpoint_probe_2022.py',
          'tools/windows_launch.py', 'control/patch_server.py']:
    ast.parse((ROOT / f).read_text(encoding='utf-8'))
print('syntax ok')
