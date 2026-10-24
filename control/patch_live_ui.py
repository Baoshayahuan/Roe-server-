# -*- coding: utf-8 -*-
"""Server-side support for the panel: configurable prep time + admin actions."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WL = ROOT / 'tools' / 'windows_launch.py'
SA = ROOT / 'server' / 'directory' / 'state_scene_actions_2022.py'
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


# ---------------------------------------------------------------- prep time
patch(WL,
      "    parser.add_argument('--services-only',action='store_true',help=argparse.SUPPRESS)",
      "    parser.add_argument('--services-only',action='store_true',help=argparse.SUPPRESS)\n"
      "    parser.add_argument('--selection-seconds',type=int,default=47,metavar='1..180',help='Preparation screen duration')",
      'wl.arg')

patch(WL,
      "'--room-template',room,'--scene-rules',str(configs['scene-'+args.mode]),'--scene-clock','--selection-seconds','47',",
      "'--room-template',room,'--scene-rules',str(configs['scene-'+args.mode]),'--scene-clock','--selection-seconds',str(args.selection_seconds),",
      'wl.value')

patch(WL,
      "    if args.advertise_ip:",
      "    if not 1 <= args.selection_seconds <= 180:\n"
      "        raise ValueError('selection-seconds: 1..180')\n"
      "    if args.advertise_ip:",
      'wl.check')

# ------------------------------------------------------- kill / revive actions
patch(SA,
      "    action = row.get('action')\n"
      "    parameter = {'set_own_health':'hp','give_ammo':'quantity','damage_npc':'damage'}.get(action)\n"
      "    if parameter is None:",
      "    action = row.get('action')\n"
      "    if action in ('kill_self', 'revive_self'):\n"
      "        allowed = {'id', 'action', 'recipient_actor_uid'}\n"
      "        if set(row) - allowed:\n"
      "            raise ValueError('State action does not accept extra fields')\n"
      "        return dict(action=action)\n"
      "    parameter = {'set_own_health':'hp','give_ammo':'quantity','damage_npc':'damage'}.get(action)\n"
      "    if parameter is None:",
      'sa.validate')

patch(SA,
      "    world,weapon = state.get('world'),state.get('weapon')\n"
      "    if world is None or weapon is None or getattr(world,'dead',False):",
      "    world,weapon = state.get('world'),state.get('weapon')\n"
      "    if request['action'] in ('kill_self', 'revive_self'):\n"
      "        if world is None:\n"
      "            return [], dict(event, reason='world_required')\n"
      "        if request['action'] == 'revive_self':\n"
      "            world.hp = world.fixture.hp\n"
      "            world.death_sent = False\n"
      "            return ([(0x1069, encode_health(state['actor_uid'], world.hp))],\n"
      "                    dict(event, accepted=True, hp=world.hp))\n"
      "        world.hp = 0\n"
      "        packets, _events = world.poll_death()\n"
      "        return packets, dict(event, accepted=True, hp=0)\n"
      "    if world is None or weapon is None or getattr(world,'dead',False):",
      'sa.apply')

for path in (WL, SA):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
