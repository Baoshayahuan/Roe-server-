# -*- coding: utf-8 -*-
"""Extend a *real* client team body with one more member (cloned record).

Instead of inventing a team, the proxy stores the body the client itself
produced for CREATE and appends a clone of that member record for the second
player (same 12 words, different uid/name).  The UI therefore renders exactly
the structure it knows.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT / 'tools' / 'roe_team_2022.py'

text = TEAM.read_text(encoding='utf-8')
if 'def with_member' in text:
    print('skip')
else:
    helper = '''

def with_member(body, uid, name):
    """Append a clone of the last member record with a new uid/name."""
    value = decode_team(body)
    if any(member_uid == uid for member_uid, _ in value['members']):
        return body
    if len(value['members']) >= 3:
        return body
    if not isinstance(name, str) or '\\0' in name:
        raise ValueError('Неверное имя участника')
    raw = name.encode('utf-8') + b'\\0'
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
        member_raw = member_name.encode('utf-8') + b'\\0'
        out += struct.pack('>QI', member_uid, len(member_raw)) + member_raw + struct.pack('>12I', *last_words)
    out += struct.pack('>QI', uid, len(raw)) + raw + struct.pack('>12I', *last_words)
    out += body[at:]
    decoded = decode_team(bytes(out))
    if len(decoded['members']) != len(members) + 1:
        raise ValueError('Не удалось добавить участника')
    return bytes(out)
'''
    TEAM.write_text(text.rstrip('\n') + helper, encoding='utf-8')
    print('patched')

ast.parse(TEAM.read_text(encoding='utf-8'))
print('syntax ok')
