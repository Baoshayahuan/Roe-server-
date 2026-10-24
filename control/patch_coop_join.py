# -*- coding: utf-8 -*-
"""Co-op matchmaking: both clients must receive MATCH_SYNC(6e2d) and JOIN(0xd77).

Previously the JOIN notification was only sent for solo training, so a co-op
queue ended with the client showing "服务器繁忙".
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / 'tools' / 'heartbeat_probe_2022.py'
text = HB.read_text(encoding='utf-8')
changed = []

old_tail = """            totals['match_found_notifications'] += 1
            capture.record('match_found', code='0x6e2d', **info)
            status()
            if join is not None and team['training'] and not join_state['sent']:
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
                status()"""

new_tail = """            totals['match_found_notifications'] += 1
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
                status()"""

if new_tail in text:
    changed.append('skip notify')
elif old_tail not in text:
    raise SystemExit('notify anchor missing')
else:
    text = text.replace(old_tail, new_tail, 1)
    changed.append('patch notify')

old_check = "                                    elif not join_state['sent'] or instance_id != join[0]:"
new_check = "                                    elif (not join_state['sent'] and not getattr(args, 'coop', False)) or instance_id != join[0]:"
if new_check in text:
    changed.append('skip d75')
elif old_check not in text:
    raise SystemExit('d75 anchor missing')
else:
    text = text.replace(old_check, new_check, 1)
    changed.append('patch d75')

HB.write_text(text, encoding='utf-8')
ast.parse(text)
print('\n'.join(changed))
print('syntax ok')
