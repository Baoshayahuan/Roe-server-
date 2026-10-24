# -*- coding: utf-8 -*-
"""Fix: the death-on-zero preview line was inserted into schema() instead of server_args()."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'control' / 'app.py'
text = APP.read_text(encoding='utf-8')

bad = ("        if self.values.get('min_own_hp') == 0 and not self.values.get('death_on_zero'):\n"
       "            cmd.append('--death-on-zero')\n")
if bad not in text:
    raise SystemExit('misplaced block not found')
text = text.replace(bad, '', 1)

marker = '    def server_args(self, client, host_profile, accounts_file, host_only):'
index = text.index(marker)
loop = text.index("        for key, label, cli, group, help_text in BOOL_FIELDS:", index)
insert = ("        if self.values.get('min_own_hp') == 0 and not self.values.get('death_on_zero'):\n"
          "            cmd.append('--death-on-zero')\n")
text = text[:loop] + insert + text[loop:]

APP.write_text(text, encoding='utf-8')
ast.parse(text)
print('fixed')
