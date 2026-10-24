# -*- coding: utf-8 -*-
"""Wire the lobby nickname patch into the proxy (idempotent)."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
text = HB.read_text(encoding='utf-8')
changes = []


def sub(old, new, tag):
    global text
    if new in text:
        changes.append('skip ' + tag)
        return
    if old not in text:
        raise SystemExit('anchor missing: ' + tag)
    text = text.replace(old, new, 1)
    changes.append('patch ' + tag)


sub("from lobby_actor_uid_2022 import LobbyActorUIDStream",
    "from lobby_actor_uid_2022 import LobbyActorUIDStream\nfrom lobby_nickname_2022 import LobbyNicknameStream",
    'import')

sub("        nickname = getattr(args, 'team_nickname', 'Player')",
    "        nickname = getattr(args, 'team_nickname', 'Player')\n        nick_stream = None",
    'var')

sub("            nickname = account['name']",
    "            nickname = account['name']\n            nick_stream = LobbyNicknameStream(key, nickname)",
    'accounts')

sub("            actor_stream = LobbyActorUIDStream(key,args.actor_uid) if getattr(args,'actor_uid',None) is not None else None",
    "            actor_stream = LobbyActorUIDStream(key,args.actor_uid) if getattr(args,'actor_uid',None) is not None else None\n"
    "            if getattr(args,'lobby_nickname',None):\n"
    "                nick_stream = LobbyNicknameStream(key, args.lobby_nickname)",
    'single')

sub("""                        if actor_stream is not None:
                            data, updates = actor_stream.feed(data)
                            for update in updates:
                                capture.record('local_actor_uid',synthetic=True,**update,**info)
                            if not data:
                                continue""",
    """                        if actor_stream is not None:
                            data, updates = actor_stream.feed(data)
                            for update in updates:
                                capture.record('local_actor_uid',synthetic=True,**update,**info)
                            if not data:
                                continue
                        if nick_stream is not None:
                            data, updates = nick_stream.feed(data)
                            for update in updates:
                                capture.record('local_nickname',synthetic=True,**update,**info)
                            if not data:
                                continue""",
    'pump')

sub("    parser.add_argument('--team-nickname', default='Player', help='Имя участника в экспериментальном ответе')",
    "    parser.add_argument('--team-nickname', default='Player', help='Имя участника в экспериментальном ответе')\n"
    "    parser.add_argument('--lobby-nickname', help='Переписать имя в lobby pre-data (без accounts-file)')",
    'arg')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changes))
print('syntax ok')
