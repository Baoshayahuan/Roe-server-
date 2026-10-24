# -*- coding: utf-8 -*-
"""Idempotent patches that turn the upstream loopback-only research stack into a
LAN/multi-account capable server, without touching game binaries.

Run:  .tools\\python\\python.exe -X utf8 control\\patch_server.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
EP = ROOT / 'server' / 'directory' / 'game_endpoint_probe_2022.py'
WL = ROOT / 'tools' / 'windows_launch.py'

changes = []


def patch(path, old, new, tag):
    text = path.read_text(encoding='utf-8')
    if new in text:
        changes.append(('skip', tag))
        return
    if old not in text:
        raise SystemExit(f'anchor not found: {tag} in {path.name}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')
    changes.append(('patch', tag))


# ---------------------------------------------------------------- heartbeat
patch(HB,
      "parser.add_argument('--port', type=int, default=8001)",
      "    parser.add_argument('--host', default='127.0.0.1', help='Bind address; 0.0.0.0 for LAN')\n"
      "    parser.add_argument('--accounts-file', type=Path, help='JSON: {accounts:[{name,actor_uid,cosmetics}], bindings:{ip:name}}')\n"
      "    parser.add_argument('--port', type=int, default=8001)",
      'hb.args')

patch(HB,
      "    server = await asyncio.start_server(handle, '127.0.0.1', args.port)",
      "    server = await asyncio.start_server(handle, args.host, args.port)",
      'hb.bind')

patch(HB,
      "    cosmetics = LocalCosmetics(cosmetic_path) if cosmetic_path else None",
      "    cosmetics = LocalCosmetics(cosmetic_path) if cosmetic_path else None\n"
      "    # Multi-account: per-connection identity chosen by IP binding or rotation.\n"
      "    accounts, bindings = [], {}\n"
      "    if getattr(args, 'accounts_file', None):\n"
      "        _acc = json.loads(Path(args.accounts_file).read_text(encoding='utf-8'))\n"
      "        accounts = _acc.get('accounts', [])\n"
      "        bindings = {str(k): str(v) for k, v in _acc.get('bindings', {}).items()}",
      'hb.accounts-load')

patch(HB,
      "        actor_stream = LobbyActorUIDStream(key,args.actor_uid) if getattr(args,'actor_uid',None) is not None else None",
      "        remote_ip = (writer.get_extra_info('peername') or ('', 0))[0]\n"
      "        account = None\n"
      "        if accounts:\n"
      "            account = next((a for a in accounts if bindings.get(remote_ip) == a['name']), None)\n"
      "            if account is None:\n"
      "                account = accounts[(totals['connections'] - 1) % len(accounts)]\n"
      "            cosmetics = LocalCosmetics(account['cosmetics'])\n"
      "            capture.record('account_assigned', profile=account['name'],\n"
      "                           actor_uid=hex(account['actor_uid']), remote=remote_ip, synthetic=True, **info)\n"
      "            actor_stream = LobbyActorUIDStream(key, account['actor_uid'])\n"
      "        else:\n"
      "            actor_stream = LobbyActorUIDStream(key,args.actor_uid) if getattr(args,'actor_uid',None) is not None else None",
      'hb.account-pick')

# ---------------------------------------------------------------- endpoint
patch(EP,
      "p.add_argument('--port',type=int,default=18001)",
      "p.add_argument('--host',default='127.0.0.1')\np.add_argument('--port',type=int,default=18001)",
      'ep.args')

patch(EP,
      "local_addr=('127.0.0.1',args.port)",
      "local_addr=(args.host,args.port)",
      'ep.bind')

# ---------------------------------------------------------------- launcher
patch(WL,
      "    parser.add_argument('--services-only',action='store_true',help=argparse.SUPPRESS)",
      "    parser.add_argument('--services-only',action='store_true',help=argparse.SUPPRESS)\n"
      "    parser.add_argument('--bind-host',default='127.0.0.1',help='127.0.0.1 or 0.0.0.0 for LAN hosting')\n"
      "    parser.add_argument('--advertise-ip',help='IP written into JOIN_INSTANCE route for remote clients')\n"
      "    parser.add_argument('--accounts-file',type=Path,help='Multi-account table for the lobby proxy')\n"
      "    parser.add_argument('--client-server',default='127.0.0.1:8001',help='-server= value for the local client')\n"
      "    parser.add_argument('--no-client',action='store_true',help='Start services only, do not launch the local client')",
      'wl.args')

patch(WL,
      "                '--local-cosmetics-config',str(configs['cosmetics']),'--actor-uid',str(account['actor_uid']),'--duration',str(args.duration+30),'--output',str(run/'lobby')])",
      "                '--local-cosmetics-config',str(configs['cosmetics']),'--actor-uid',str(account['actor_uid']),'--duration',str(args.duration+30),'--output',str(run/'lobby'),\n"
      "                '--host',args.bind_host]+(['--accounts-file',str(args.accounts_file)] if args.accounts_file else []))",
      'wl.proxy')

patch(WL,
      "                '--environment-config',str(configs['environment']),",
      "                '--environment-config',str(configs['environment']),'--host',args.bind_host,",
      'wl.endpoint')

patch(WL,
      "    if args.remote_peer:\n        check_ports([(8001,socket.SOCK_STREAM),(19001,socket.SOCK_STREAM),(18001,socket.SOCK_DGRAM)])",
      "    if args.advertise_ip:\n"
      "        join_copy = json.loads(configs['join'].read_text(encoding='utf-8'))\n"
      "        join_copy['response']['route'] = '0:%s:18001' % args.advertise_ip\n"
      "        configs['join'].write_text(json.dumps(join_copy, ensure_ascii=False, indent=2), encoding='utf-8')\n"
      "        print('JOIN route advertised as %s:18001' % args.advertise_ip, flush=True)\n"
      "    if args.remote_peer:\n        check_ports([(8001,socket.SOCK_STREAM),(19001,socket.SOCK_STREAM),(18001,socket.SOCK_DGRAM)])",
      'wl.advertise')

patch(WL,
      "            game=subprocess.Popen([str(runtime/'Europa_Client.exe'),'-language=en','-garena','-uid=1','-server=127.0.0.1:8001'],cwd=runtime,stdout=client_log,stderr=subprocess.STDOUT)",
      "            game=subprocess.Popen([str(runtime/'Europa_Client.exe'),'-language=en','-garena','-uid=1','-server='+args.client_server],cwd=runtime,stdout=client_log,stderr=subprocess.STDOUT)",
      'wl.client-server')

print('\n'.join(f'{kind:5s} {tag}' for kind, tag in changes))
