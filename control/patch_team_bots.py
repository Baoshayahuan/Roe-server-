# -*- coding: utf-8 -*-
"""Wire team bots + minimum HP into the launcher and lobby proxy."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
WL = ROOT / 'tools' / 'windows_launch.py'
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


# ------------------------------------------------------------------ proxy
patch(HB,
      "from lobby_nickname_2022 import LobbyNicknameStream",
      "from lobby_nickname_2022 import LobbyNicknameStream\n"
      "import sys as _sys\n"
      "_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'server' / 'directory'))\n"
      "from team_bots_2022 import bot_members",
      'hb.import')

patch(HB,
      "    parser.add_argument('--lobby-nickname', help='Переписать имя в lobby pre-data (без accounts-file)')",
      "    parser.add_argument('--lobby-nickname', help='Переписать имя в lobby pre-data (без accounts-file)')\n"
      "    parser.add_argument('--team-bots', type=int, default=0, metavar='0..2', help='Static AI teammates in the squad list')",
      'hb.arg')

patch(HB,
      "                                        team['body'] = team_body(uid, body, nickname)",
      "                                        bots = int(getattr(args, 'team_bots', 0) or 0)\n"
      "                                        members = bot_members(uid, nickname, bots) if bots else None\n"
      "                                        team['body'] = team_body(uid, body, nickname, members=members)\n"
      "                                        if bots:\n"
      "                                            capture.record('team_bots', count=bots, members=[hex(u) for u, _ in members], **info)",
      'hb.team')

# ------------------------------------------------------------------ launcher
patch(WL,
      "    parser.add_argument('--no-client',action='store_true',help='Start services only, do not launch the local client')",
      "    parser.add_argument('--no-client',action='store_true',help='Start services only, do not launch the local client')\n"
      "    parser.add_argument('--team-bots',type=int,default=0,metavar='0..2',help='Static AI teammates (squad max 3)')\n"
      "    parser.add_argument('--min-own-hp',type=int,default=None,metavar='0..1000',help='Player HP floor')",
      'wl.args')

patch(WL,
      "                '--host',args.bind_host]+(['--accounts-file',str(args.accounts_file)] if args.accounts_file else [])+(['--allow-remote-route'] if args.advertise_ip else []))",
      "                '--host',args.bind_host]+(['--accounts-file',str(args.accounts_file)] if args.accounts_file else [])"
      "+(['--allow-remote-route'] if args.advertise_ip else [])"
      "+(['--team-bots',str(args.team_bots)] if args.team_bots else []))",
      'wl.proxy')

patch(WL,
      "    if not 1 <= args.selection_seconds <= 180:",
      "    if not 0 <= args.team_bots <= 2:\n"
      "        raise ValueError('team-bots: 0..2')\n"
      "    if args.team_bots and args.target == 'none':\n"
      "        raise ValueError('team-bots требует -Target plain/armored (пассивные актёры сцены)')\n"
      "    if args.min_own_hp is not None and not 0 <= args.min_own_hp <= 1000:\n"
      "        raise ValueError('min-own-hp: 0..1000')\n"
      "    if not 1 <= args.selection_seconds <= 180:",
      'wl.check')

patch(WL,
      "    if args.advertise_ip:",
      "    if args.min_own_hp is not None:\n"
      "        world_copy = json.loads(configs['world'].read_text(encoding='utf-8'))\n"
      "        world_copy['hp_floor'] = args.min_own_hp\n"
      "        configs['world'].write_text(json.dumps(world_copy, ensure_ascii=False, indent=2), encoding='utf-8')\n"
      "        print('HP floor set to %d' % args.min_own_hp, flush=True)\n"
      "    if args.advertise_ip:",
      'wl.hp')

for path in (HB, WL):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
