"""Прокси localhost:8001→9001 с необязательным экспериментальным heartbeat-ответом."""
import argparse
import asyncio
import datetime as dt
import json
import signal
from pathlib import Path
import sys
import struct
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'server/directory'))
from listener import Capture
from roe_protocol_2022 import FrameBuffer, client_heartbeat, heartbeat_reply, server_stamp, dt_plain
from roe_team_2022 import client_message, server_message, team_body, with_member
from roe_join_instance_2022 import (
    JoinInstanceNotification, JoinInstanceResponse,
    encode_join_instance_notification, encode_join_instance_response,
    decode_join_instance_request,
)
import ipaddress
from local_cosmetics_2022 import LocalCosmetics
from roe_clock_2022 import LobbyClockStream
from lobby_actor_uid_2022 import LobbyActorUIDStream
from lobby_nickname_2022 import LobbyNicknameStream
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'server' / 'directory'))
from team_bots_2022 import bot_members
import struct as _struct


def _live_cosmetics(path, cosmetics, profile, account_uid=None):
    """Mirror the current avatar selection for the scene endpoint."""
    try:
        value = dict(profile=profile,
                     avatar=list(_struct.unpack('>5I', cosmetics.avatar)),
                     avatar_applied=bool(cosmetics.avatar_applied))
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(value)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(target)
        if account_uid:
            per = target.parent / ('live-cosmetics-%d.json' % account_uid)
            tmp2 = per.with_suffix('.tmp')
            tmp2.write_text(text, encoding='utf-8')
            tmp2.replace(per)
    except (OSError, ValueError):
        pass


def live_cosmetics_path(output):
    return Path(output).parent / 'live-cosmetics.json'


def load_join_experiment(path, allow_remote=False):
    """Явные синтетические поля; loopback по умолчанию, LAN-режим разрешает IPv4."""
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    notification = JoinInstanceNotification(**value['notification'])
    response = dict(value['response'])
    prefix, address, port = response['route'].split(':')
    if (not ipaddress.IPv4Address(address).is_loopback and not allow_remote) or not 1 <= int(port) <= 65535:
        raise ValueError('JOIN_INSTANCE: требуется loopback endpoint')
    response['route'] = response['route'].encode('ascii')
    for name in ('block_88', 'block_98'):
        response[name] = bytes.fromhex(response[name])
    response = JoinInstanceResponse(**response)
    delay = value['delay_after_found']
    if type(delay) not in (float, int) or not 0 <= delay <= 60:
        raise ValueError('JOIN_INSTANCE: задержка должна быть от 0 до 60 секунд')
    return notification.instance_id, encode_join_instance_notification(notification), encode_join_instance_response(response), delay


async def serve(args, ready=None, stop=None):
    team_enabled = getattr(args, 'team_reply', False)
    nickname = getattr(args, 'team_nickname', 'Player')
    novice = getattr(args, 'novice_state', None)
    training_enabled = getattr(args, 'training_reply', False)
    if novice is not None and (not team_enabled or novice not in (0, 1, 2)):
        raise ValueError('novice-state требует team-reply и значение 0/1/2')
    match_enabled = getattr(args, 'match_reply', False)
    if training_enabled and (not match_enabled or novice != 1):
        raise ValueError('training-reply требует match-reply и novice-state=1')
    estimate = getattr(args, 'match_estimate', 640)
    found_delay = getattr(args, 'match_found_delay', None)
    if found_delay is not None and (not match_enabled or found_delay < 0):
        raise ValueError('match-found-delay требует match-reply и неотрицательную задержку')
    if match_enabled and not team_enabled:
        raise ValueError('Для match-reply нужен team-reply')
    cosmetic_path = getattr(args, 'local_cosmetics_config', None)
    cosmetics = LocalCosmetics(cosmetic_path) if cosmetic_path else None
    # Multi-account: per-connection identity chosen by IP binding or rotation.
    accounts, bindings = [], {}
    if getattr(args, 'accounts_file', None):
        _acc = json.loads(Path(args.accounts_file).read_text(encoding='utf-8'))
        accounts = _acc.get('accounts', [])
        bindings = {str(k): str(v) for k, v in _acc.get('bindings', {}).items()}
    join = load_join_experiment(getattr(args, 'join_instance_config', None), getattr(args, 'allow_remote_route', False))
    if join is not None and (not training_enabled or found_delay is None):
        raise ValueError('JOIN_INSTANCE требует training-reply и match-found-delay')
    if not 0 <= estimate <= 0xffffffff:
        raise ValueError('Оценка ожидания должна быть U32')
    key = args.session_key_file.read_bytes()
    if len(key) != 16:
        raise ValueError('Файл session key должен содержать ровно 16 бинарных байт')
    run = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-heartbeat-'+uuid.uuid4().hex[:8]
    capture = Capture(args.output/run)
    if stop is None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        # В фоне оболочка может игнорировать SIGINT; задаём явное завершение захвата.
        if sys.platform != 'win32':
            for signum in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(signum, stop.set)
    tasks = set()
    roster = {}  # connection -> (uid, name); shared by all lobby connections
    team_template = {'body': None}  # last real CREATE body from a client
    by_ip = {}   # remote ip -> account name (sticky across reconnects)

    def coop_squad(self_uid, self_name):
        members, seen = [(self_uid, self_name)], {self_uid}
        for member_uid, member_name in roster.values():
            if member_uid and member_uid not in seen:
                seen.add(member_uid)
                members.append((member_uid, member_name))
        return members[:2]
    sockets = {}  # connection -> StreamWriter, for room broadcasts
    totals = {'connections': 0, 'heartbeat_requests': 0, 'heartbeat_replies': 0, 'inspection_errors': 0, 'team_replies': 0, 'match_replies': 0, 'match_found_notifications': 0, 'novice_notifications': 0, 'join_notifications': 0, 'join_requests': 0, 'join_responses': 0}

    def status():
        value = {'state': 'running', 'reply_enabled': args.reply, 'team_reply_enabled': team_enabled, 'match_reply_enabled': match_enabled, 'novice_state': novice, 'training_reply_enabled': training_enabled, **totals}
        path = capture.directory/'status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)

    async def handle(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        connection = uuid.uuid4().hex[:12]
        info = {'connection': connection}
        clock_stream = LobbyClockStream(key) if getattr(args,'local_server_clock',False) else None
        remote_ip = (writer.get_extra_info('peername') or ('', 0))[0]
        nickname = getattr(args, 'team_nickname', 'Player')
        nick_stream = None
        account = None
        if accounts:
            account = next((a for a in accounts if bindings.get(remote_ip) == a['name']), None)
            if account is None and by_ip.get(remote_ip):
                account = next((a for a in accounts if a['name'] == by_ip[remote_ip]), None)
            if account is None:
                account = next((a for a in accounts if a['name'] not in by_ip.values()), None)
            if account is None:
                account = accounts[(totals['connections'] - 1) % len(accounts)]
            by_ip[remote_ip] = account['name']
            cosmetics = LocalCosmetics(account['cosmetics'])
            nickname = account['name']
            nick_stream = LobbyNicknameStream(key, nickname)
            _live_cosmetics(live_cosmetics_path(args.output), cosmetics, account['name'], account['actor_uid'])
            capture.record('account_assigned', profile=account['name'],
                           actor_uid=hex(account['actor_uid']), remote=remote_ip, synthetic=True, **info)
            actor_stream = LobbyActorUIDStream(key, account['actor_uid'])
        else:
            actor_stream = LobbyActorUIDStream(key,args.actor_uid) if getattr(args,'actor_uid',None) is not None else None
            if getattr(args,'lobby_nickname',None):
                nick_stream = LobbyNicknameStream(key, args.lobby_nickname)
        totals['connections'] += 1
        sockets[connection] = writer
        capture.record('connect', **info, remote=writer.get_extra_info('peername'))
        status()
        upstream = None
        pumps = []
        outgoing = asyncio.Lock()
        clock = {'stamp': None, 'at': None}
        frames = {'client_to_server': FrameBuffer(), 'server_to_client': FrameBuffer()}
        enabled = {'client_to_server': True, 'server_to_client': True}
        last_counter = None
        team = {'uid': None, 'body': None, 'searching': False, 'generation': 0, 'novice_sent': False, 'training': False, 'cosmetics_sent': False}
        join_state = {'sent': False, 'replied': False}
        async def notify_found(generation):
            await asyncio.sleep(found_delay)
            if not team['searching'] or team['generation'] != generation or writer.is_closing():
                return
            if not enabled['server_to_client'] or clock['stamp'] is None:
                return
            stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
            response = server_message(0x6e2d, struct.pack('>I', 0), stamp, key)
            async with outgoing:
                writer.write(response)
                capture.record('data', response, direction='server_to_client', origin='match_probe', **info)
                await writer.drain()
            team['searching'] = False
            totals['match_found_notifications'] += 1
            capture.record('match_found', code='0x6e2d', **info)
            status()
            coop = bool(getattr(args, 'coop', False))
            if coop:
                # Все клиенты комнаты должны увидеть MATCH_SYNC, иначе второй
                # остаётся в лобби и получает "сервер занят" при входе.
                for other_id, other in list(sockets.items()):
                    if other_id == connection or other.is_closing():
                        continue
                    other.write(server_message(0x6e2d, struct.pack('>I', 0), stamp, key))
                await asyncio.gather(*[w.drain() for k, w in list(sockets.items())
                                       if k != connection and not w.is_closing()], return_exceptions=True)
                capture.record('coop_match_sync', recipients=len(sockets) - 1, synthetic=True, **info)
            if join is not None and (team['training'] or coop) and not join_state['sent']:
                await asyncio.sleep(join[3])
                if team['generation'] != generation or writer.is_closing() or not enabled['server_to_client']:
                    return
                stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                response = server_message(0xd77, join[1], stamp, key)
                async with outgoing:
                    writer.write(response)
                    # Состояние выставляется до drain: запрос может прийти немедленно.
                    join_state['sent'] = True
                    capture.record('data', response, direction='server_to_client', origin='join_probe', **info)
                    await writer.drain()
                totals['join_notifications'] += 1
                capture.record('join_notification', instance_id=join[0], synthetic=True, **info)
                if coop:
                    for other_id, other in list(sockets.items()):
                        if other_id == connection or other.is_closing():
                            continue
                        other.write(server_message(0xd77, join[1], stamp, key))
                    await asyncio.gather(*[w.drain() for k, w in list(sockets.items())
                                           if k != connection and not w.is_closing()], return_exceptions=True)
                    capture.record('coop_join_push', instance_id=join[0], synthetic=True, **info)
                status()

        try:
            up_reader, upstream = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', args.upstream_port), 5)

            async def pump(source, destination, direction):
                nonlocal last_counter
                while data := await source.read(65536):
                    # По умолчанию передаём исходные байты. Явный режим меняет
                    # только UNIX timestamp1f5f до первой установки native epoch.
                    if direction == 'server_to_client':
                        if clock_stream is not None:
                            data,updates=clock_stream.feed(data)
                            for update in updates:
                                capture.record('local_server_clock',synthetic=True,**update,**info)
                            if not data:
                                continue
                        if actor_stream is not None:
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
                                continue
                        async with outgoing:
                            destination.write(data)
                            capture.record('data', data, direction=direction, origin='upstream', **info)
                            await destination.drain()
                    else:
                        destination.write(data)
                        capture.record('data', data, direction=direction, origin='client', **info)
                        await destination.drain()
                    if not enabled[direction]:
                        continue
                    try:
                        for frame in frames[direction].feed(data):
                            if direction == 'server_to_client':
                                stamp = server_stamp(frame, key)
                                if stamp is not None:
                                    clock.update(stamp=stamp, at=time.monotonic())
                                if team_enabled:
                                    plain = dt_plain(frame, key)
                                    if cosmetics and plain and len(plain) >= 10:
                                        # Порядок штатной инициализации нужен для поиска
                                        # позднего сброса wardrobe. Только opcode/длина,
                                        # без AUTH, UID и содержимого чужого сообщения.
                                        upstream_code = struct.unpack_from('>H', plain, 4)[0]
                                        if upstream_code != 0x1f75:
                                            capture.record('cosmetic_upstream_order', code=hex(upstream_code),
                                                           body_length=len(plain)-10, **info)
                                    if plain and len(plain) == 39 and struct.unpack_from('>H', plain, 4)[0] == 0x32b:
                                        # ENTER_GAME_RSP payload+12 задаёт UID последующих заголовков.
                                        if struct.unpack_from('>I', plain, 30)[0] == 0:
                                            team['uid'] = struct.unpack_from('>Q', plain, 22)[0]
                                            roster[connection] = (team['uid'], nickname)
                                            if cosmetics and team['uid'] and not team['cosmetics_sent']:
                                                async with outgoing:
                                                    for code, body in cosmetics.initial(team['uid']):
                                                        response = server_message(code, body, stamp, key)
                                                        writer.write(response)
                                                        capture.record('data', response, direction='server_to_client', origin='local_cosmetics', **info)
                                                    await writer.drain()
                                                team['cosmetics_sent'] = True
                                                capture.record('cosmetics_issued', gun_skins=len(cosmetics.ids), characters=len(cosmetics.characters), accessories=len(cosmetics.accessories), clothes=len(cosmetics.clothes), **info)
                                            if novice is not None and team['uid'] and not team['novice_sent']:
                                                response = server_message(0x6e35, struct.pack('>I', novice), stamp, key)
                                                async with outgoing:
                                                    writer.write(response)
                                                    capture.record('data', response, direction='server_to_client', origin='training_probe', **info)
                                                    await writer.drain()
                                                team['novice_sent'] = True
                                                totals['novice_notifications'] += 1
                                                capture.record('novice_notification', value=novice, code='0x6e35', **info)
                                                status()
                                continue
                            if cosmetics and team['cosmetics_sent'] and enabled['server_to_client']:
                                message = client_message(frame, key)
                                if message and message[1] == team['uid']:
                                    # Метаданные действий гардероба: неизвестные тела,
                                    # AUTH и идентификаторы аккаунта не журналируем.
                                    if message[0] not in (0x1f75,0x1f5e,0x71ae,0x1b59):
                                        capture.record('cosmetic_client_order',code=hex(message[0]),length=len(message[2]),**info)
                                    if message[0] in range(0x73a1,0x73ba) or message[0] in (0x48a,0x54df,0x54e2) or message[0] == 0x3e80 and len(message[2]) == 10:
                                        capture.record('cosmetic_request', code=hex(message[0]), length=len(message[2]), fields_hex=message[2].hex() if len(message[2]) <= 128 else None, **info)
                                        if message[0] in (0x6e29, 0x6e2b, 0x6e2d):
                                            capture.record('match_body', code=hex(message[0]), body_hex=message[2].hex(), fields=list(struct.unpack('%dI' % (len(message[2])//4), message[2][:len(message[2])//4*4])) if len(message[2]) % 4 == 0 else None, **info)
                                    replies, action = cosmetics.handle(message[0], message[2],message[1])
                                    _live_cosmetics(live_cosmetics_path(args.output), cosmetics, nickname,
                                                    account['actor_uid'] if account else None)
                                    if action:
                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                        async with outgoing:
                                            for code, body in replies:
                                                response = server_message(code, body, stamp, key)
                                                writer.write(response)
                                                capture.record('data', response, direction='server_to_client', origin='local_cosmetics', **info)
                                            await writer.drain()
                                        capture.record('cosmetic_action', action=action, request=hex(message[0]), selected=dict(cosmetics.selected), **info)
                            if team_enabled:
                                message = client_message(frame, key)
                                if message and message[0] in (0x701d, 0x702f):
                                    code, uid, body = message
                                    reason = None
                                    if (not team['uid'] or uid != team['uid']) and not getattr(args, 'coop', False):
                                        reason = 'UID не совпал с ENTER_GAME_RSP'
                                    elif not enabled['server_to_client'] or clock['stamp'] is None:
                                        reason = 'Нет проверенного серверного потока'
                                    elif code == 0x702f and team['body'] is None and not getattr(args, 'coop', False):
                                        reason = 'Команда ещё не создана; PULL_INFO до CREATE пропущен'
                                    if reason:
                                        capture.record('team_skipped', code=hex(code), reason=reason, **info)
                                    else:
                                        bots = int(getattr(args, 'team_bots', 0) or 0)
                                        if code == 0x701d:
                                            if bots:
                                                members = bot_members(uid, nickname, bots)
                                            elif (getattr(args, 'coop', False)
                                                  and getattr(args, 'coop_team_sync', False)):
                                                members = None  # client body kept; peer added on relay
                                            else:
                                                members = None
                                            team['body'] = team_body(uid, body, nickname, members=members)
                                            if members is None or members == []:
                                                team_template['body'] = team['body']
                                            elif getattr(args, 'coop_team_sync', False):
                                                team_template['body'] = team['body']
                                            if bots:
                                                capture.record('team_bots', count=bots,
                                                               members=[hex(u) for u, _ in members], **info)
                                        elif (getattr(args, 'coop', False)
                                              and getattr(args, 'coop_team_sync', False)):
                                            if team['body'] is None and team_template['body'] is None:
                                                members = coop_squad(uid, nickname)
                                                team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),
                                                                         nickname, members=members)
                                                capture.record('coop_pull_info', count=len(members), **info)
                                            if team_template['body'] is not None:
                                                # relay the creator's own body verbatim (no cloning)
                                                team['body'] = team_template['body']
                                                capture.record('coop_team_raw', source='template', **info)
                                            elif team['body'] is None:
                                                members = coop_squad(uid, nickname)
                                                team['body'] = team_body(uid, struct.pack('>4I', 1, 16010, 1, 2),
                                                                         nickname, members=members)
                                                capture.record('coop_pull_info', count=len(members), **info)
                                        if team['body'] is None:
                                            capture.record('team_empty', code=hex(code),
                                                           coop=getattr(args, 'coop', False),
                                                           team_sync=getattr(args, 'coop_team_sync', False), **info)
                                            status()
                                            continue
                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                        reply_code = 0x701e if code == 0x701d else 0x7030
                                        response = server_message(reply_code, team['body'], stamp, key)
                                        async with outgoing:
                                            writer.write(response)
                                            capture.record('data', response, direction='server_to_client', origin='team_probe', **info)
                                            await writer.drain()
                                        if (getattr(args, 'coop', False)
                                                and getattr(args, 'coop_team_sync', False)):
                                            for other_id, other in list(sockets.items()):
                                                if other_id == connection or other.is_closing():
                                                    continue
                                                other.write(server_message(reply_code, team['body'], stamp, key))
                                                capture.record('data', b'', direction='server_to_client', origin='team_broadcast', connection=other_id)
                                            await asyncio.gather(*[w.drain() for w in list(sockets.values()) if not w.is_closing()], return_exceptions=True)
                                        totals['team_replies'] += 1
                                        capture.record('team_reply', request_code=hex(code), code=hex(reply_code), payload_length=len(team['body']), **info)
                                    status()
                            if getattr(args, 'coop', False):
                                message = client_message(frame, key)
                                if message and message[0] in (0x7021, 0x702d):
                                    fcode, fuid, fbody = message
                                    if enabled['server_to_client'] and clock['stamp'] is not None:
                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                        reply = 0x7022 if fcode == 0x7021 else 0x702e
                                        payload = struct.pack('>II', 0, 0)
                                        response = server_message(reply, payload, stamp, key)
                                        async with outgoing:
                                            writer.write(response)
                                            capture.record('data', response, direction='server_to_client',
                                                           origin='friend_probe', **info)
                                            await writer.drain()
                                        capture.record('friend_probe', code=hex(fcode), reply=hex(reply),
                                                       request_length=len(fbody), **info)
                            if match_enabled:
                                message = client_message(frame, key)
                                if message and message[0] in (0x6e29, 0x6e2b):
                                    code, uid, body = message
                                    reason = None
                                    if not team['uid'] or uid != team['uid']:
                                        reason = 'UID не совпал с ENTER_GAME_RSP'
                                    elif not enabled['server_to_client'] or clock['stamp'] is None:
                                        reason = 'Нет проверенного серверного потока'
                                    elif team['body'] is None and not getattr(args, 'coop', False) and not (
                                            training_enabled and team['novice_sent'] and
                                            ((code == 0x6e29 and body == struct.pack('>5I', 1, 1, 1, 2, 16023)) or
                                             (code == 0x6e2b and team['training']))):
                                        reason = 'Команда ещё не создана'
                                    elif len(body) != (20 if code == 0x6e29 else 1):
                                        reason = 'Непроверенная длина запроса подбора'
                                    elif code == 0x6e2b and not team['searching']:
                                        reason = 'Подбор ещё не запущен'
                                    if reason:
                                        capture.record('match_skipped', code=hex(code), reason=reason, **info)
                                    else:
                                        # Официальный 6e2a: type/result/estimate-seconds, 6e2c: result.
                                        bots = int(getattr(args, 'team_bots', 0) or 0)
                                        if (bots and code == 0x6e29 and team['body'] is None
                                                and struct.unpack_from('>I', body, 16)[0] == 16023):
                                            create_body = struct.pack('>4I', 1, 16023, 1, 2)
                                            team['body'] = team_body(uid, create_body, nickname,
                                                                     members=bot_members(uid, nickname, bots))
                                            stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                            pushed = server_message(0x701e, team['body'], stamp, key)
                                            async with outgoing:
                                                writer.write(pushed)
                                                capture.record('data', pushed, direction='server_to_client', origin='forced_team', **info)
                                                await writer.drain()
                                            team['forced_training'] = True
                                            capture.record('forced_team', count=bots + 1, members=[hex(u) for u, _ in bot_members(uid, nickname, bots)], **info)
                                        if getattr(args, 'coop', False) and code == 0x6e29:
                                            peers = [(u, n) for u, n in roster.values() if u]
                                            members = [(uid, nickname)] + [(u, n) for u, n in peers if u != uid]
                                            seen, unique = set(), []
                                            for member_uid, member_name in members:
                                                if member_uid in seen:
                                                    continue
                                                seen.add(member_uid)
                                                unique.append((member_uid, member_name))
                                            map_id = struct.unpack_from('>I', body, 16)[0]
                                            create_body = struct.pack('>4I', 1, map_id, 1, 2)
                                            team['body'] = team_body(uid, create_body, nickname, members=unique[:3])
                                            if clock['stamp'] is not None:
                                                stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                                payload = team['body']
                                                for other_id, other in list(sockets.items()):
                                                    if other.is_closing():
                                                        continue
                                                    other.write(server_message(0x701e, payload, stamp, key))
                                                await asyncio.gather(*[w.drain() for w in list(sockets.values()) if not w.is_closing()], return_exceptions=True)
                                            capture.record('coop_team_push', count=len(unique[:3]),
                                                           members=[hex(u) for u, _ in unique[:3]], **info)
                                        if code == 0x6e29:
                                            match_type = struct.unpack_from('>I', body)[0]
                                            payload = struct.pack('>III', match_type, 0, estimate)
                                            reply_code = 0x6e2a
                                        else:
                                            payload = struct.pack('>I', 0)
                                            reply_code = 0x6e2c
                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                        response = server_message(reply_code, payload, stamp, key)
                                        async with outgoing:
                                            writer.write(response)
                                            capture.record('data', response, direction='server_to_client', origin='match_probe', **info)
                                            await writer.drain()
                                        if code == 0x6e29:
                                            team['training'] = team['body'] is None or team.get('forced_training')
                                            # Адрес и ответ JOIN принадлежат одному подбору,
                                            # а не всему TCP-соединению. Новый принятый поиск
                                            # после ReturnLobby должен снова выдать D77/D76.
                                            join_state.update(sent=False, replied=False)
                                        team['generation'] += 1
                                        team['searching'] = code == 0x6e29
                                        if code == 0x6e29 and found_delay is not None:
                                            pumps.append(asyncio.create_task(notify_found(team['generation'])))
                                        totals['match_replies'] += 1
                                        capture.record('match_reply', request_code=hex(code), code=hex(reply_code), payload_length=len(payload), **info)
                                    status()
                            if join is not None:
                                message = client_message(frame, key)
                                if message and message[0] == 0xd75:
                                    code, uid, body = message
                                    totals['join_requests'] += 1
                                    instance_id = decode_join_instance_request(body)
                                    reason = None
                                    if uid != team['uid'] or not team['uid']:
                                        reason = 'UID не совпал с ENTER_GAME_RSP'
                                    elif (not join_state['sent'] and not getattr(args, 'coop', False)) or instance_id != join[0]:
                                        reason = 'Не совпал instance ID отправленного уведомления'
                                    elif join_state['replied']:
                                        reason = 'Повторный JOIN_INSTANCE_REQ'
                                    elif not enabled['server_to_client'] or clock['stamp'] is None:
                                        reason = 'Нет проверенного серверного потока'
                                    if reason:
                                        capture.record('join_skipped', reason=reason, **info)
                                    else:
                                        stamp = (clock['stamp'] + int((time.monotonic()-clock['at'])*25)) & 0xffffffff
                                        response = server_message(0xd76, join[2], stamp, key)
                                        async with outgoing:
                                            writer.write(response)
                                            join_state['replied'] = True
                                            capture.record('data', response, direction='server_to_client', origin='join_probe', **info)
                                            await writer.drain()
                                        totals['join_responses'] += 1
                                        capture.record('join_response', instance_id=instance_id, synthetic=True, **info)
                                    status()
                            counter = client_heartbeat(frame, key)
                            if counter is None:
                                continue
                            totals['heartbeat_requests'] += 1
                            capture.record('heartbeat_request', counter=counter, **info)
                            if args.reply and enabled['server_to_client'] and clock['stamp'] is not None and counter != last_counter:
                                elapsed = time.monotonic()-clock['at']
                                stamp = (clock['stamp'] + int(elapsed*25)) & 0xffffffff
                                response = heartbeat_reply(counter, stamp, key)
                                async with outgoing:
                                    writer.write(response)
                                    capture.record('data', response, direction='server_to_client', origin='heartbeat_probe', **info)
                                    await writer.drain()
                                last_counter = counter
                                totals['heartbeat_replies'] += 1
                                capture.record('heartbeat_reply', counter=counter, stamp=stamp, **info)
                            elif args.reply and (not enabled['server_to_client'] or clock['stamp'] is None):
                                capture.record('heartbeat_skipped', reason='Нет проверенного серверного потока', **info)
                            status()
                    except ValueError as exc:
                        # Ошибка анализа выключает инъекцию направления, но не пересылку.
                        enabled[direction] = False
                        totals['inspection_errors'] += 1
                        capture.record('inspection_error', direction=direction, error=str(exc), **info)
                        status()
                if direction == 'server_to_client' and clock_stream is not None:
                    clock_stream.finish()
                if direction == 'server_to_client' and actor_stream is not None:
                    actor_stream.finish()
                if destination.can_write_eof():
                    destination.write_eof()
                capture.record('eof', direction=direction, **info)

            pumps = [asyncio.create_task(pump(reader, upstream, 'client_to_server')),
                     asyncio.create_task(pump(up_reader, writer, 'server_to_client'))]
            await asyncio.gather(*pumps)
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            capture.record('connection_error', error=str(exc), **info)
        finally:
            roster.pop(connection, None)
            sockets.pop(connection, None)
            for pump_task in pumps:
                pump_task.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for stream in (writer, upstream):
                if stream:
                    stream.close()
                    try:
                        await stream.wait_closed()
                    except OSError:
                        pass
            capture.record('disconnect', **info)
            tasks.discard(task)
            status()

    try:
        server = await asyncio.start_server(handle, args.host, args.port)
        async with server:
            binding = server.sockets[0].getsockname()
            capture.record('ready', bindings={'tcp': binding}, upstream=['127.0.0.1', args.upstream_port], reply_enabled=args.reply)
            status()
            if ready:
                ready.set_result((binding, capture.directory))
            if args.duration:
                try:
                    await asyncio.wait_for(stop.wait(), args.duration)
                except asyncio.TimeoutError:
                    pass
            else:
                await stop.wait()
    finally:
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)
        status()
        state = json.loads((capture.directory/'status.json').read_text())
        state['state'] = 'stopped'
        (capture.directory/'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        capture.record('stopped', **totals)
        capture.events.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-cosmetics-config', type=Path, help='Локальный каталог владения скинами оружия2022')
    parser.add_argument('--actor-uid',type=lambda value:int(value,0),help='Явный UID одного локального клиента в ENTER_GAME32B; не multiplayer/профиль аккаунта')
    parser.add_argument('--local-server-clock', action='store_true', help='Заменить архивный UNIX timestamp первого lobby1f5f текущим временем')
    parser.add_argument('--session-key-file', required=True, type=Path)
    parser.add_argument('--reply', action='store_true', help='Добавлять экспериментальные ответы 0x1f75')
    parser.add_argument('--team-reply', action='store_true', help='Экспериментальные CREATE/PULL_INFO ответы одного участника')
    parser.add_argument('--match-reply', action='store_true', help='Экспериментальные начало/отмена подбора; требует team-reply')
    parser.add_argument('--match-found-delay', type=float, help='Через N секунд отправить тестовый MATCH_SYNC=0; требует match-reply')
    parser.add_argument('--match-estimate', type=int, default=640, help='Оценка ожидания в секундах, U32')
    parser.add_argument('--training-reply', action='store_true', help='Разрешить наблюдённый Solo Training без CREATE; требует match-reply и novice-state=1')
    parser.add_argument('--join-instance-config', type=Path, help='Явные синтетические NOTIFY/RSP для loopback опыта после Training Match Found')
    parser.add_argument('--novice-state', type=int, choices=(0, 1, 2), help='Тестовый MATCH_NOVICE_SYNC после ENTER_GAME; требует team-reply')
    parser.add_argument('--team-nickname', default='Player', help='Имя участника в экспериментальном ответе')
    parser.add_argument('--lobby-nickname', help='Переписать имя в lobby pre-data (без accounts-file)')
    parser.add_argument('--team-bots', type=int, default=0, metavar='0..2', help='Static AI teammates in the squad list')
    parser.add_argument('--coop', action='store_true', help='Share the squad between connected players')
    parser.add_argument('--coop-team-sync', action='store_true', help='Experimental: inject a synthetic squad')
    parser.add_argument('--host', default='127.0.0.1', help='Bind address; 0.0.0.0 for LAN')
    parser.add_argument('--accounts-file', type=Path, help='JSON: {accounts:[{name,actor_uid,cosmetics}], bindings:{ip:name}}')
    parser.add_argument('--allow-remote-route', action='store_true', help='Allow non-loopback JOIN route (LAN hosting)')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--upstream-port', type=int, default=9001)
    parser.add_argument('--duration', type=float, default=180)
    parser.add_argument('--output', type=Path, default=ROOT/'captures')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not 1 <= args.upstream_port <= 65535 or args.port == args.upstream_port or args.duration < 0:
        parser.error('Некорректные порты или длительность')
    if args.actor_uid is not None and not 0 < args.actor_uid < 2**64:
        parser.error('actor-uid требует ненулевой U64')
    if args.training_reply and (not args.match_reply or args.novice_state != 1):
        parser.error('--training-reply требует --match-reply и --novice-state 1')
    if args.novice_state is not None and not args.team_reply:
        parser.error('--novice-state требует --team-reply')
    if args.match_found_delay is not None and (not args.match_reply or args.match_found_delay < 0):
        parser.error('--match-found-delay требует --match-reply и неотрицательную задержку')
    if args.match_reply and not args.team_reply:
        parser.error('--match-reply требует --team-reply')
    if not 0 <= args.match_estimate <= 0xffffffff:
        parser.error('--match-estimate должен быть U32')
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
