# -*- coding: utf-8 -*-
"""Endpoint half of the live-cosmetics patch (indentation-sensitive)."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
text = EP.read_text(encoding='utf-8')

anchor = (
    "                                    if self.weapon_fixture and self.weapon_fixture.cosmetics_config_file:\n"
    "                                        data, appearance = apply_room_cosmetics(data,self.weapon_fixture.cosmetics_config_file)\n"
)
replacement = (
    "                                    if self.weapon_fixture and self.weapon_fixture.cosmetics_config_file:\n"
    "                                        live = self.capture.directory.parent/'live-cosmetics.json'\n"
    "                                        override = None\n"
    "                                        if live.is_file():\n"
    "                                            try:\n"
    "                                                override = json.loads(live.read_text(encoding='utf-8'))\n"
    "                                            except (OSError, ValueError):\n"
    "                                                override = None\n"
    "                                        data, appearance = apply_room_cosmetics(data,self.weapon_fixture.cosmetics_config_file,override)\n"
)

if "live-cosmetics.json" in text:
    print('skip ep.live')
elif anchor not in text:
    raise SystemExit('anchor missing')
else:
    EP.write_text(text.replace(anchor, replacement, 1), encoding='utf-8')
    print('patch ep.live')

ast.parse(EP.read_text(encoding='utf-8'))
print('syntax ok')
