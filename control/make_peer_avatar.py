# -*- coding: utf-8 -*-
"""Create config/peer-avatar.json (template for remote players) from a target fixture."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server' / 'directory'))
from actor_probe_2022 import ActorFixture  # noqa: E402

base = json.loads((ROOT / 'config' / 'target-plain.json').read_text(encoding='utf-8'))
base['uid'] = '0x2040000200001'
base['speed_cm_seconds'] = 0
base['waypoints'] = [[365030, 543960, 259111]]
base['pellet_damage'] = 0
base.pop('attack', None)
base['collision_boxes'] = []
target = ROOT / 'config' / 'peer-avatar.json'
target.write_text(json.dumps(base, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

fixture = ActorFixture.load(target)
print('peer-avatar ok: uid=0x%x speed=%s hp=%s' % (fixture.uid, fixture.speed, fixture.hp))
