# -*- coding: utf-8 -*-
"""Make the synthetic squad opt-in (default off).

Forcing a team body broke the lobby UI (duplicate members, "[object Object]",
stuck Ready button).  Squads are now only injected when `--coop-team-sync` is
explicitly enabled; default co-op keeps each client's own team untouched.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
WL = ROOT / 'tools' / 'windows_launch.py'
APP = ROOT / 'control' / 'app.py'
changed = []


def patch(path, old, new, tag):
    text = path.read_text(encoding='utf-8')
    if new in text:
        changed.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit(f'anchor missing: {tag} in {path.name}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    changed.append('patch ' + tag)


# proxy: gate every synthetic squad on the new flag

patch(HB,
      "                                            elif getattr(args, 'coop', False):\n"
      "                                                members = coop_squad(uid, nickname)",
      "                                            elif (getattr(args, 'coop', False)\n"
      "                                                  and getattr(args, 'coop_team_sync', False)):\n"
      "                                                members = coop_squad(uid, nickname)",
      'create-gate')

patch(HB,
      "                                        elif team['body'] is None and getattr(args, 'coop', False):",
      "                                        elif (team['body'] is None and getattr(args, 'coop', False)\n"
      "                                              and getattr(args, 'coop_team_sync', False)):",
      'pullinfo-gate')

patch(HB,
      "                                        if getattr(args, 'coop', False):\n"
      "                                            for other_id, other in list(sockets.items()):",
      "                                        if (getattr(args, 'coop', False)\n"
      "                                                and getattr(args, 'coop_team_sync', False)):\n"
      "                                            for other_id, other in list(sockets.items()):",
      'broadcast-gate')

patch(HB,
      "    parser.add_argument('--coop', action='store_true', help='Share the squad between connected players')",
      "    parser.add_argument('--coop', action='store_true', help='Share the squad between connected players')\n"
      "    parser.add_argument('--coop-team-sync', action='store_true', help='Experimental: inject a synthetic squad')",
      'hb.arg')

# launcher: pass-through
patch(WL,
      "    parser.add_argument('--peer-listing-type',type=int,default=1,metavar='0..255',help='565 listing byte 13 for peers')",
      "    parser.add_argument('--peer-listing-type',type=int,default=1,metavar='0..255',help='565 listing byte 13 for peers')\n"
      "    parser.add_argument('--coop-team-sync',action='store_true',help='Experimental synthetic squad')",
      'wl.arg')

patch(WL,
      "+(['--coop'] if args.coop else [])",
      "+(['--coop'] if args.coop else [])+(['--coop-team-sync'] if getattr(args,'coop_team_sync',False) else [])",
      'wl.pass')

# panel: setting (default off)
patch(APP,
      "    ('coop', '双人联机（场景同步）', '--coop', 'net', '开启后场景同步其他玩家；会关闭门/可破坏物与自定义战利品表'),",
      "    ('coop', '双人联机（场景同步）', '--coop', 'net', '开启后场景同步其他玩家；会关闭门/可破坏物与自定义战利品表'),\n"
      "    ('coop_team_sync', '强制共享队伍（实验）', '--coop-team-sync', 'net', '服务端伪造队伍报文；可能让大厅 UI 异常（出现 [object Object] / 无法准备），默认关'),",
      'app.field')

for path in (HB, WL, APP):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changed))
print('syntax ok')
