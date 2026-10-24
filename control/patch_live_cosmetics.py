# -*- coding: utf-8 -*-
"""Propagate the lobby character selection into the scene room response.

Problem: the lobby proxy saves the selection into the *per-connection account*
state file, while the UDP endpoint builds ENTER_ROOM_RSP from the run-level
catalog (host account).  With several accounts, or when the host account is not
the one the client logged in with, the scene receives avatar ids [0,0,0,0,0]
and the player spawns as the default model.

Fix: the proxy mirrors the live selection to ``runs/<id>/live-cosmetics.json``
and the endpoint prefers that file when patching the room response.
"""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
RC = ROOT / 'server' / 'directory' / 'room_cosmetics_2022.py'
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


# 1. lobby proxy: mirror the live selection next to the run directory
patch(HB,
      "from lobby_nickname_2022 import LobbyNicknameStream",
      "from lobby_nickname_2022 import LobbyNicknameStream\n"
      "import struct as _struct\n"
      "\n"
      "\n"
      "def _live_cosmetics(path, cosmetics, profile):\n"
      "    \"\"\"Mirror the current avatar selection for the scene endpoint.\"\"\"\n"
      "    try:\n"
      "        value = dict(profile=profile,\n"
      "                     avatar=list(_struct.unpack('>5I', cosmetics.avatar)),\n"
      "                     avatar_applied=bool(cosmetics.avatar_applied))\n"
      "        target = Path(path)\n"
      "        target.parent.mkdir(parents=True, exist_ok=True)\n"
      "        temporary = target.with_suffix('.tmp')\n"
      "        temporary.write_text(json.dumps(value), encoding='utf-8')\n"
      "        temporary.replace(target)\n"
      "    except (OSError, ValueError):\n"
      "        pass\n"
      "\n"
      "\n"
      "def live_cosmetics_path(output):\n"
      "    return Path(output).parent / 'live-cosmetics.json'",
      'hb.helper')

patch(HB,
      "            nickname = account['name']\n            nick_stream = LobbyNicknameStream(key, nickname)",
      "            nickname = account['name']\n"
      "            nick_stream = LobbyNicknameStream(key, nickname)\n"
      "            _live_cosmetics(live_cosmetics_path(args.output), cosmetics, account['name'])",
      'hb.initial')

patch(HB,
      "                            replies, action = cosmetics.handle(message[0], message[2],message[1])",
      "                            replies, action = cosmetics.handle(message[0], message[2],message[1])\n"
      "                            _live_cosmetics(live_cosmetics_path(args.output), cosmetics, nickname)",
      'hb.handle')

# 2. room template patcher accepts an explicit selection
patch(RC,
      "def apply_room_cosmetics(payload, catalog_path):",
      "def apply_room_cosmetics(payload, catalog_path, override=None):",
      'rc.signature')

patch(RC,
      "    cosmetics = LocalCosmetics(catalog_path)",
      "    cosmetics = LocalCosmetics(catalog_path)\n"
      "    if override:\n"
      "        ids = override.get('avatar')\n"
      "        if isinstance(ids, list) and len(ids) == 5 and all(isinstance(x, int) for x in ids):\n"
      "            cosmetics.avatar = struct.pack('>5I', *ids)\n"
      "        cosmetics.avatar_applied = bool(override.get('avatar_applied'))",
      'rc.override')

# 3. endpoint prefers the live file
patch(EP,
      "            if self.weapon_fixture and self.weapon_fixture.cosmetics_config_file:\n"
      "                data, appearance = apply_room_cosmetics(data,self.weapon_fixture.cosmetics_config_file)",
      "            if self.weapon_fixture and self.weapon_fixture.cosmetics_config_file:\n"
      "                live = self.capture.directory.parent/'live-cosmetics.json'\n"
      "                override = None\n"
      "                if live.is_file():\n"
      "                    try:\n"
      "                        override = json.loads(live.read_text(encoding='utf-8'))\n"
      "                    except (OSError, ValueError):\n"
      "                        override = None\n"
      "                data, appearance = apply_room_cosmetics(data,self.weapon_fixture.cosmetics_config_file,override)",
      'ep.live')

for name, path in (('hb', HB), ('ep', EP), ('rc', RC)):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
