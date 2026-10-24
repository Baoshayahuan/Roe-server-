# -*- coding: utf-8 -*-
"""Stop health probes from consuming accounts, and make the account pick sticky per IP.

* Panel: TCP ports are checked through netstat instead of opening a connection
  (every probe connection used to be assigned a lobby account).
* Proxy: a given remote IP keeps its account across reconnects; rotation only
  happens for a new IP.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'control' / 'app.py'
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


patch(APP,
      "def listen_ports():\n    return {'8001': port_open(8001), '9001': port_open(9001), '18001': udp_in_use(18001)}",
      "_PORTS_CACHE = {'at': 0.0, 'value': None}\n\n\n"
      "def listen_ports():\n"
      "    \"\"\"Listening state without opening connections (probes would consume lobby accounts).\"\"\"\n"
      "    now = time.time()\n"
      "    if _PORTS_CACHE['value'] is not None and now - _PORTS_CACHE['at'] < 1.0:\n"
      "        return _PORTS_CACHE['value']\n"
      "    listening = set()\n"
      "    try:\n"
      "        out = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True,\n"
      "                             encoding='mbcs', errors='replace', timeout=5).stdout\n"
      "        for line in out.splitlines():\n"
      "            if 'LISTENING' not in line:\n"
      "                continue\n"
      "            for port in ('8001', '9001'):\n"
      "                if (':' + port + ' ') in line:\n"
      "                    listening.add(port)\n"
      "    except (OSError, subprocess.SubprocessError):\n"
      "        pass\n"
      "    value = {'8001': '8001' in listening, '9001': '9001' in listening, '18001': udp_in_use(18001)}\n"
      "    _PORTS_CACHE['at'], _PORTS_CACHE['value'] = now, value\n"
      "    return value",
      'app.ports')

patch(HB,
      "    roster = {}  # connection -> (uid, name); shared by all lobby connections",
      "    roster = {}  # connection -> (uid, name); shared by all lobby connections\n"
      "    by_ip = {}   # remote ip -> account name (sticky across reconnects)",
      'hb.byip')

patch(HB,
      "            account = next((a for a in accounts if bindings.get(remote_ip) == a['name']), None)\n"
      "            if account is None:\n"
      "                account = accounts[(totals['connections'] - 1) % len(accounts)]",
      "            account = next((a for a in accounts if bindings.get(remote_ip) == a['name']), None)\n"
      "            if account is None and by_ip.get(remote_ip):\n"
      "                account = next((a for a in accounts if a['name'] == by_ip[remote_ip]), None)\n"
      "            if account is None:\n"
      "                account = next((a for a in accounts if a['name'] not in by_ip.values()), None)\n"
      "            if account is None:\n"
      "                account = accounts[(totals['connections'] - 1) % len(accounts)]\n"
      "            by_ip[remote_ip] = account['name']",
      'hb.sticky')

for path in (APP, HB):
    ast.parse(path.read_text(encoding='utf-8'))
print('\n'.join(changes))
print('syntax ok')
