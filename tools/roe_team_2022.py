# -*- coding: utf-8 -*-
"""Lobby team body (player + optional AI teammates).

The original upstream body carried exactly one member.  This version keeps the
same layout but allows 1..3 records so the squad panel can show teammates.

Layout: result/team-id/mode/leader/unknown/count, then per member
(uid Q, name length I, name+NUL, 12 x u32), then
(unknown, map_id, perspective, 5) and a trailing u32.
"""
import struct
from roe_protocol_2022 import dt_plain, encrypt, MAGIC


def client_message(frame, key):
    plain = dt_plain(frame, key)
    if plain is None:
        return None
    if frame[3] != 4 or len(plain) < 34:
        raise ValueError('Неизвестный формат клиентского DT')
    length, code = struct.unpack_from('>IH', plain, 4)
    if length != len(plain) - 4 or code != struct.unpack_from('>I', plain, 30)[0]:
        raise ValueError('Не совпала длина или body-tag')
    return code, struct.unpack_from('>Q', plain, 22)[0], plain[34:]


def server_message(code, body, stamp, key):
    plain = struct.pack('>IHI', stamp, code, code) + body
    cipher = encrypt(plain, key)
    return MAGIC + b'\0\0' + struct.pack('>II', 12, len(cipher)) + cipher


def team_body(uid, request, nickname='Player', team_id=1, members=None):
    if not 0 < uid < 2**64 or not 0 < team_id < 2**64:
        raise ValueError('Нужны ненулевые идентификаторы')
    if len(request) != 16:
        raise ValueError('CREATE_REQ должен содержать четыре U32')
    mode, map_id, perspective, unknown = struct.unpack('>IIII', request)
    records = list(members) if members else [(uid, nickname)]
    if not 1 <= len(records) <= 3:
        raise ValueError('Команда: 1..3 участников')
    encoded, seen = [], set()
    for member_uid, name in records:
        if type(member_uid) is not int or not 0 < member_uid < 2**64 or member_uid in seen:
            raise ValueError('Неверный или повторный UID участника')
        seen.add(member_uid)
        if not isinstance(name, str) or '\0' in name:
            raise ValueError('Неверное имя участника')
        raw = name.encode('utf-8') + b'\0'
        if not 1 <= len(raw) <= 128:
            raise ValueError('Имя должно занимать 1…128 байт с NUL')
        encoded.append((member_uid, raw))
    # Result; team-id/type/leader/unknown/count. Два UID согласованы с ENTER_GAME.
    prefix = struct.pack('>IQIQII', 0, team_id, mode, uid, 0, len(encoded))
    words = (0, 2, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0)
    body = bytearray(prefix)
    for member_uid, raw in encoded:
        body += struct.pack('>QI', member_uid, len(raw)) + raw + struct.pack('>12I', *words)
    body += struct.pack('>4I', unknown, map_id, perspective, 5)
    body += struct.pack('>I', 0)
    return bytes(body)


def decode_team(body):
    """Strict reader for 1..3 members."""
    if len(body) < 52:
        raise ValueError('Недостаточно данных')
    result, team_id, mode, leader, unknown, count = struct.unpack_from('>IQIQII', body)
    if not 1 <= count <= 3:
        raise ValueError('Ожидается 1..3 участника')
    at = 32
    members = []
    for _ in range(count):
        member_uid, length = struct.unpack_from('>QI', body, at)
        at += 12
        if not 1 <= length <= 128:
            raise ValueError('Неверная длина записи')
        name = body[at:at + length]
        at += length
        if name[-1] != 0 or b'\0' in name[:-1]:
            raise ValueError('Неверная NUL-строка')
        struct.unpack_from('>12I', body, at)
        at += 48
        members.append((member_uid, name[:-1].decode('utf-8')))
    tail = struct.unpack_from('>4I', body, at)
    at += 16
    if struct.unpack_from('>I', body, at)[0] != 0 or at + 4 != len(body):
        raise ValueError('Дополнительный список должен быть пуст')
    return dict(result=result, team_id=team_id, mode=mode, leader=leader,
                unknown=unknown, members=members, tail=tail)


def decode_minimal_team(body):
    value = decode_team(body)
    if len(value['members']) != 1:
        raise ValueError('Ожидается один участник')
    return dict(result=value['result'], team_id=value['team_id'], mode=value['mode'],
                leader=value['leader'], uid=value['members'][0][0],
                nickname=value['members'][0][1], unknown=value['unknown'],
                tail=value['tail'])

def with_member(body, uid, name):
    """Append a clone of the last member record with a new uid/name."""
    value = decode_team(body)
    if any(member_uid == uid for member_uid, _ in value['members']):
        return body
    if len(value['members']) >= 3:
        return body
    if not isinstance(name, str) or '\0' in name:
        raise ValueError('Неверное имя участника')
    raw = name.encode('utf-8') + b'\0'
    if not 1 <= len(raw) <= 128:
        raise ValueError('Имя должно занимать 1…128 байт с NUL')
    members = list(value['members'])
    # locate the last record and reuse its 12 words
    at = 32
    last_words = None
    for _ in members:
        member_uid, length = struct.unpack_from('>QI', body, at)
        at += 12
        at += length
        last_words = struct.unpack_from('>12I', body, at)
        at += 48
    if last_words is None:
        raise ValueError('Пустое тело команды')
    prefix = bytearray(body[:32])
    struct.pack_into('>I', prefix, 28, len(members) + 1)
    out = bytearray(prefix)
    for member_uid, member_name in members:
        member_raw = member_name.encode('utf-8') + b'\0'
        out += struct.pack('>QI', member_uid, len(member_raw)) + member_raw + struct.pack('>12I', *last_words)
    out += struct.pack('>QI', uid, len(raw)) + raw + struct.pack('>12I', *last_words)
    out += body[at:]
    decoded = decode_team(bytes(out))
    if len(decoded['members']) != len(members) + 1:
        raise ValueError('Не удалось добавить участника')
    return bytes(out)
