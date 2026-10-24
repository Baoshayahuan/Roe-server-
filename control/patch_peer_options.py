# -*- coding: utf-8 -*-
"""1) listing type (565 byte 13) becomes an option, default 1
2) per-account cosmetics mirror so one player's wardrobe can't overwrite the other's
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
WL = ROOT / 'tools' / 'windows_launch.py'
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
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


# ---- endpoint: configurable listing type
patch(EP,
      "        if self.peer_avatars is not None and shared_ground_loot:\n            self.peer_avatars.listing_type = 1  # co-op: mark peers as friendly (experiment)",
      "        if self.peer_avatars is not None and shared_ground_loot:\n"
      "            self.peer_avatars.listing_type = int(getattr(self, 'peer_listing_type', 1) or 0)",
      'ep.listing')

patch(EP,
      "def __init__(self, capture, handshake=False, ident=False, grant=False, auth=False, room_template=None, scene_rules=None, scene_clock=False, selection_seconds=None,",
      "def __init__(self, capture, handshake=False, ident=False, grant=False, auth=False, room_template=None, scene_rules=None, scene_clock=False, selection_seconds=None, peer_listing_type=1,",
      'ep.signature')

patch(EP,
      "        self.selection_seconds = selection_seconds",
      "        self.selection_seconds = selection_seconds\n        self.peer_listing_type = peer_listing_type",
      'ep.field')

patch(EP,
      "rules,args.scene_clock,args.selection_seconds,",
      "rules,args.scene_clock,args.selection_seconds,getattr(args,'peer_listing_type',1),",
      'ep.call')

patch(EP,
      "    p.add_argument('--peer-avatar-config',type=Path,help='Аватары комнаты и выбранные позы; общий лут/HP отдельными флагами')",
      "    p.add_argument('--peer-avatar-config',type=Path,help='Аватары комнаты и выбранные позы; общий лут/HP отдельными флагами')\n"
      "    p.add_argument('--peer-listing-type',type=int,default=1,metavar='0..255',help='565 listing byte 13 for replicated peers')",
      'ep.arg')

# ---- launcher: pass it in co-op
patch(WL,
      "'--peer-avatar-trajectories','--peer-equipment'] if args.coop else []),",
      "'--peer-avatar-trajectories','--peer-equipment','--peer-listing-type',str(args.peer_listing_type)] if args.coop else []),",
      'wl.pass')

patch(WL,
      "    parser.add_argument('--coop',action='store_true',help='Two-player co-op: scene peer replication, no doors/breakables')",
      "    parser.add_argument('--coop',action='store_true',help='Two-player co-op: scene peer replication, no doors/breakables')\n"
      "    parser.add_argument('--peer-listing-type',type=int,default=1,metavar='0..255',help='565 listing byte 13 for peers')",
      'wl.arg')

# ---- proxy: per-account cosmetics files
patch(HB,
      "def _live_cosmetics(path, cosmetics, profile):",
      "def _live_cosmetics(path, cosmetics, profile, account_uid=None):",
      'hb.sig')

patch(HB,
      "        target = Path(path)\n"
      "        target.parent.mkdir(parents=True, exist_ok=True)\n"
      "        temporary = target.with_suffix('.tmp')\n"
      "        temporary.write_text(json.dumps(value), encoding='utf-8')\n"
      "        temporary.replace(target)",
      "        target = Path(path)\n"
      "        target.parent.mkdir(parents=True, exist_ok=True)\n"
      "        text = json.dumps(value)\n"
      "        temporary = target.with_suffix('.tmp')\n"
      "        temporary.write_text(text, encoding='utf-8')\n"
      "        temporary.replace(target)\n"
      "        if account_uid:\n"
      "            per = target.parent / ('live-cosmetics-%d.json' % account_uid)\n"
      "            tmp2 = per.with_suffix('.tmp')\n"
      "            tmp2.write_text(text, encoding='utf-8')\n"
      "            tmp2.replace(per)",
      'hb.write')

patch(HB,
      "            _live_cosmetics(live_cosmetics_path(args.output), cosmetics, account['name'])",
      "            _live_cosmetics(live_cosmetics_path(args.output), cosmetics, account['name'], account['actor_uid'])",
      'hb.init-call')

patch(HB,
      "                                    _live_cosmetics(live_cosmetics_path(args.output), cosmetics, nickname)",
      "                                    _live_cosmetics(live_cosmetics_path(args.output), cosmetics, nickname,\n"
      "                                                    account['actor_uid'] if account else None)",
      'hb.action-call')

for path in (EP, WL, HB):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
