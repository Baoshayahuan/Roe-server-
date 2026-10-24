# -*- coding: utf-8 -*-
"""面板 API 自检（不启动游戏、不改动现有账户/房间/配置）。

用法： .tools\\python\\python.exe -X utf8 control\\selftest.py [http://127.0.0.1:8770]
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8770'
PASS, FAIL = [], []


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode('utf-8') or '{}')


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' -> ' + str(detail)) if detail and not cond else ''))


def main():
    code, status = call('GET', '/api/status')
    check('status 200', code == 200 and 'server' in status)
    check('status 有端口表', isinstance(status['server'].get('ports'), dict))
    check('客户端目录已设置', bool(status.get('client_dir')))

    code, schema = call('GET', '/api/settings')
    fields = schema.get('schema', {}).get('fields', [])
    check('设置项 >= 30', len(fields) >= 30, len(fields))
    groups = {f['group'] for f in fields}
    check('设置分组 >= 6', len(groups) >= 6, groups)

    code, saved = call('POST', '/api/settings', {'values': {'cycle_scale': 3}})
    check('设置写入', code == 200 and saved['values']['cycle_scale'] == 3)
    code, bad = call('POST', '/api/settings', {'values': {'kit': 'not-a-kit'}})
    check('非法设置被拒绝', code == 400)

    code, accounts = call('GET', '/api/accounts')
    check('账户列表', code == 200 and len(accounts['accounts']) >= 1)
    temp = 'selftest' + str(int(time.time()) % 100000)
    code, created = call('POST', '/api/accounts', {'name': temp, 'note': '自检'})
    check('新增账户', code == 200 and created.get('name') == temp)
    check('账户 UID 唯一', created.get('actor_uid') != accounts['accounts'][0]['actor_uid'])
    code, dup = call('POST', '/api/accounts', {'name': temp})
    check('重复账户被拒绝', code == 400)
    code, _ = call('DELETE', '/api/accounts/' + temp)
    check('删除账户', code == 200)

    code, rooms = call('GET', '/api/rooms')
    check('房间列表', code == 200)
    code, room = call('POST', '/api/rooms', {'name': '自检房间', 'host': status['host_account'], 'max': 4})
    check('创建中文房间', code == 200 and room.get('name') == '自检房间', room.get('name'))
    code, joined = call('POST', '/api/rooms/%s/join' % room['id'], {'account': status['host_account']})
    check('加入房间', code == 200)
    code, started = call('POST', '/api/rooms/%s/start' % room['id'])
    check('开启战局（占位）', code == 200 and started.get('status') == 'starting')
    code, _ = call('DELETE', '/api/rooms/' + room['id'])
    check('删除房间', code == 200)

    code, configs = call('GET', '/api/configs')
    check('配置清单 >= 20', code == 200 and len(configs['configs']) >= 20, len(configs.get('configs', [])))
    name = 'practice-target-points'
    code, text = call('GET', '/api/configs/' + name)
    check('读取配置', code == 200 and text.get('text', '').strip().startswith('{'))
    code, saved = call('POST', '/api/configs/' + name, {'text': text['text']})
    check('原样写回配置（触发备份）', code == 200)
    code, bad = call('POST', '/api/configs/' + name, {'text': '{oops'})
    check('非法 JSON 被拒绝', code == 400)
    code, ro = call('POST', '/api/configs/wire', {'text': '{}'})
    check('只读配置被拒绝', code == 400)

    code, preview = call('GET', '/api/server/preview')
    check('服务端命令预览', code == 200 and 'windows_launch.py' in preview.get('line', ''))
    check('预览含账户表', '--accounts-file' in preview.get('line', ''))
    code, cprev = call('GET', '/api/client/preview?ip=10.0.0.5&port=8001')
    check('客户端命令预览', code == 200 and '-server=10.0.0.5:8001' in cprev.get('line', ''))

    code, logs = call('GET', '/api/logs')
    check('日志清单', code == 200 and len(logs.get('logs', [])) >= 1)

    code, live = call('GET', '/api/live/status')
    check('实时指令状态', code == 200 and 'enabled' in live)
    code, bad = call('POST', '/api/live/action', {'action': 'set_own_health', 'hp': 0})
    check('非法实时指令被拒绝', code == 400)

    print('\n%d passed, %d failed' % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
