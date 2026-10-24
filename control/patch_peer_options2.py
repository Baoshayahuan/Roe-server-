# -*- coding: utf-8 -*-
"""Room cosmetics: prefer the per-account mirror, fall back to the shared one."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
APP = ROOT / 'control' / 'app.py'
changes = []


def patch(path, old, new, tag):
    text = path.read_text(encoding='utf-8')
    if new in text:
        changes.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit(f'anchor missing: {tag} in {path.name}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    changes.append('patch ' + tag)


patch(EP,
      "                                        live = self.capture.directory.parent/'live-cosmetics.json'\n"
      "                                        override = None\n"
      "                                        if live.is_file():",
      "                                        base = self.capture.directory.parent\n"
      "                                        live = base/('live-cosmetics-%d.json' % state['actor_uid'])\n"
      "                                        if not live.is_file():\n"
      "                                            live = base/'live-cosmetics.json'\n"
      "                                        override = None\n"
      "                                        if live.is_file():",
      'ep.per-account')

patch(APP,
      "    ('client_server', '本机客户端连接', 'text', '127.0.0.1:8001', None, '--client-server', 'net', '本机客户端 -server= 值'),",
      "    ('client_server', '本机客户端连接', 'text', '127.0.0.1:8001', None, '--client-server', 'net', '本机客户端 -server= 值'),\n"
      "    ('peer_listing_type', '队友标记字节', 'int', 1, {'min': 0, 'max': 255}, '--peer-listing-type', 'net', '565 列表第 13 字节：0=不标记，1=当前最顺（默认），2=候选试验'),",
      'app.field')

for path in (EP, APP):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
