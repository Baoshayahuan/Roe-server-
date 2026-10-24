# -*- coding: utf-8 -*-
"""Two-player co-op wiring: peer avatars + shared HP + shared ground loot.

* `--coop` on the launcher (panel sets it) enables the scene peer replication.
* Door/breakable fixtures are skipped in co-op (the endpoint rejects them).
* The lobby proxy shares one team body between connected players so both see a
  2-person squad.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
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


# ---------------------------------------------------------------- proxy roster
patch(HB,
      "    tasks = set()",
      "    tasks = set()\n"
      "    roster = {}  # connection -> (uid, name); shared by all lobby connections",
      'hb.roster')

patch(HB,
      "            capture.record('account_assigned', profile=account['name'],",
      "            capture.record('account_assigned', profile=account['name'],",
      'hb.noop')

patch(HB,
      "                                        bots = int(getattr(args, 'team_bots', 0) or 0)\n"
      "                                        members = bot_members(uid, nickname, bots) if bots else None\n"
      "                                        team['body'] = team_body(uid, body, nickname, members=members)",
      "                                        bots = int(getattr(args, 'team_bots', 0) or 0)\n"
      "                                        if bots:\n"
      "                                            members = bot_members(uid, nickname, bots)\n"
      "                                        elif getattr(args, 'coop', False):\n"
      "                                            peers = [(u, n) for u, n in roster.values() if u and u != uid]\n"
      "                                            members = [(uid, nickname)] + peers[:2]\n"
      "                                        else:\n"
      "                                            members = None\n"
      "                                        team['body'] = team_body(uid, body, nickname, members=members)",
      'hb.team-roster')

# register the player's UID once the lobby hands it out
patch(HB,
      "                                            team['uid'] = struct.unpack_from('>Q', plain, 22)[0]",
      "                                            team['uid'] = struct.unpack_from('>Q', plain, 22)[0]\n"
      "                                            roster[connection] = (team['uid'], nickname)",
      'hb.register')

patch(HB,
      "    parser.add_argument('--team-bots', type=int, default=0, metavar='0..2', help='Static AI teammates in the squad list')",
      "    parser.add_argument('--team-bots', type=int, default=0, metavar='0..2', help='Static AI teammates in the squad list')\n"
      "    parser.add_argument('--coop', action='store_true', help='Share the squad between connected players')",
      'hb.coop-arg')

# ---------------------------------------------------------------- launcher
patch(WL,
      "    parser.add_argument('--team-bots',type=int,default=0,metavar='0..2',help='Static AI teammates (squad max 3)')",
      "    parser.add_argument('--team-bots',type=int,default=0,metavar='0..2',help='Static AI teammates (squad max 3)')\n"
      "    parser.add_argument('--coop',action='store_true',help='Two-player co-op: scene peer replication, no doors/breakables')",
      'wl.coop-arg')

patch(WL,
      "                '--environment-config',str(configs['environment']),'--host',args.bind_host,",
      "                '--environment-config',str(configs['environment']),'--host',args.bind_host,\n"
      "                *(['--peer-avatar-config',str(ROOT/'config/peer-avatar.json'),'--shared-ground-loot','--shared-peer-health'] if args.coop else []),",
      'wl.endpoint-peer')

patch(WL,
      "            if 'winter-breakables' in configs:\n"
      "                command+=['--breakable-config',str(configs['winter-breakables'])]\n"
      "            if 'winter-doors' in configs:\n"
      "                command+=['--door-config',str(configs['winter-doors'])]",
      "            if 'winter-breakables' in configs and not args.coop:\n"
      "                command+=['--breakable-config',str(configs['winter-breakables'])]\n"
      "            if 'winter-doors' in configs and not args.coop:\n"
      "                command+=['--door-config',str(configs['winter-doors'])]",
      'wl.coop-doors')

patch(WL,
      "                '--host',args.bind_host]+(['--accounts-file',str(args.accounts_file)] if args.accounts_file else [])",
      "                '--host',args.bind_host]+(['--accounts-file',str(args.accounts_file)] if args.accounts_file else [])"
      "+(['--coop'] if args.coop else [])",
      'wl.proxy-coop')

for path in (WL, HB):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
