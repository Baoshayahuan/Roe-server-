# -*- coding: utf-8 -*-
"""min-own-hp = 0 must actually allow death: enable death-on-zero automatically."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WL = ROOT / 'tools' / 'windows_launch.py'
APP = ROOT / 'control' / 'app.py'
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


patch(WL,
      "    if args.min_own_hp is not None and not 0 <= args.min_own_hp <= 1000:\n"
      "        raise ValueError('min-own-hp: 0..1000')",
      "    if args.min_own_hp is not None and not 0 <= args.min_own_hp <= 1000:\n"
      "        raise ValueError('min-own-hp: 0..1000')\n"
      "    if args.min_own_hp == 0 and not args.death_on_zero:\n"
      "        args.death_on_zero = True\n"
      "        print('HP floor 0 -> zero-HP death enabled', flush=True)",
      'wl.death-coupling')

patch(APP,
      "('min_own_hp', '最低血量', 'int', 100, {'min': 0, 'max': 1000}, '--min-own-hp', 'loadout', '玩家血量下限：伤害不会把血量打到该值以下；0 = 可以被打死，100 = 默认教学值')",
      "('min_own_hp', '最低血量', 'int', 100, {'min': 0, 'max': 1000}, '--min-own-hp', 'loadout', '玩家血量下限：伤害不会把血量打到该值以下；0 = 可以被打死（自动开启零血即死），100 = 默认教学值')",
      'app.help')

for path in (WL, APP):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
