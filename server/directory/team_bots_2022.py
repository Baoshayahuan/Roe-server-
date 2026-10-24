# -*- coding: utf-8 -*-
"""Two static AI teammates: lobby squad records + scene targets with the same UID."""
from pathlib import Path
import json

# Scene-style UIDs, distinct from the practice targets (0x20400008000xx).
BOT_UID_BASE = 0x2040000900000
# Same area as the smoke loot / practice stand, on the Iceland terrain.
BOT_POSITIONS = (
    (365150, 543960, 259111),
    (364910, 543960, 259111),
)


def bot_uids(count):
    if not 0 <= count <= 2:
        raise ValueError('人机队友数量 0..2')
    return [BOT_UID_BASE + index for index in range(count)]


def bot_members(player_uid, nickname, count):
    """[(uid, name)] for the lobby team body."""
    uids = bot_uids(count)
    return [(player_uid, nickname)] + [(uid, 'Bot%d' % (index + 1)) for index, uid in enumerate(uids)]


def bot_points(count, root=None):
    """passive_targets entries so the scene spawns exactly these bots."""
    uids = bot_uids(count)
    points = json.loads((Path(root) / 'config' / 'practice-target-points.json').read_text(encoding='utf-8'))
    template = points['targets'][0]['position'] if points.get('targets') else list(BOT_POSITIONS[0])
    out = []
    for index, uid in enumerate(uids):
        base = BOT_POSITIONS[index] if index < len(BOT_POSITIONS) else tuple(template)
        out.append(dict(uid=hex(uid), position=list(base)))
    return out
