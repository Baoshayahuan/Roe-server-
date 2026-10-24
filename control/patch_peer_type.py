# -*- coding: utf-8 -*-
"""Experiment: mark replicated peers as friendly via the 565 listing type byte.

The listing fixture is 23 bytes; byte 13 is the only unexplained slot.  Old
research suspected it encodes the relationship (0 = neutral/unknown).  In co-op
we set it to 1 and log the change so it can be reverted quickly.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / 'server' / 'directory' / 'peer_avatar_2022.py'
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
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


patch(PA,
      "        self.next_avatar = 0x2040000100001\n        self.pose_bootstrap = {}",
      "        self.next_avatar = 0x2040000100001\n        self.pose_bootstrap = {}\n"
      "        self.listing_type = 0  # 565 listing byte 13; co-op sets 1 (friendly experiment)",
      'pa.field')

patch(PA,
      "        struct.pack_into('>Q',listing,14,uid)",
      "        struct.pack_into('>Q',listing,14,uid)\n"
      "        if self.listing_type:\n"
      "            listing[13] = self.listing_type",
      'pa.byte')

patch(EP,
      "        self.peer_avatars = PeerAvatarRooms(peer_avatar_fixture, shared_peer_health, peer_avatar_trajectories, peer_equipment) if peer_avatar_fixture else None",
      "        self.peer_avatars = PeerAvatarRooms(peer_avatar_fixture, shared_peer_health, peer_avatar_trajectories, peer_equipment) if peer_avatar_fixture else None\n"
      "        if self.peer_avatars is not None and shared_ground_loot:\n"
      "            self.peer_avatars.listing_type = 1  # co-op: mark peers as friendly (experiment)",
      'ep.type')

for path in (PA, EP):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
