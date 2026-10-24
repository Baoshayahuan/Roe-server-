# -*- coding: utf-8 -*-
"""ROE 本地服务端控制面板 —— 后端（仅标准库）。

职责：
  * 启停服务端（windows_launch.py）与客户端（Europa_Client.exe）
  * 账户增删、IP 绑定
  * 全部服务端设置的读取/分类/写回
  * 房间/组队数据（后端统一战局暂未实现）
  * 日志、状态、本机 IP

启动： .tools\\python\\python.exe -X utf8 control\\app.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / 'control'
WEB = CONTROL / 'web'
STATE = CONTROL / 'state'
LOGS = STATE / 'logs'
BACKUPS = STATE / 'backups'
RUNS = ROOT / 'runs'
PY = ROOT / '.tools' / 'python' / 'python.exe'
DOTNET = ROOT / '.tools' / 'dotnet' / 'dotnet.exe'
LAUNCH = ROOT / 'tools' / 'windows_launch.py'
DEFAULT_CLIENT = Path(os.environ.get('ROE_CLIENT', ''))
APP_PORT = 8770

for d in (STATE, LOGS, BACKUPS):
    d.mkdir(parents=True, exist_ok=True)

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


# --------------------------------------------------------------------------- util
def now_iso():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def port_open(port, host='127.0.0.1', timeout=0.35):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def local_ips():
    out = []
    try:
        for line in subprocess.run(['ipconfig'], capture_output=True, text=True,
                                   encoding='mbcs', errors='replace').stdout.splitlines():
            m = re.search(r'IPv4[^\d]*([\d.]+)', line)
            if m and m.group(1) not in out:
                out.append(m.group(1))
    except OSError:
        pass
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in out and not ip.startswith('127.'):
                out.append(ip)
    except OSError:
        pass
    return out


def udp_in_use(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


_PORTS_CACHE = {'at': 0.0, 'value': None}


def listen_ports():
    """Listening state without opening connections (probes would consume lobby accounts)."""
    now = time.time()
    if _PORTS_CACHE['value'] is not None and now - _PORTS_CACHE['at'] < 1.0:
        return _PORTS_CACHE['value']
    listening = set()
    try:
        out = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True,
                             encoding='mbcs', errors='replace', timeout=5).stdout
        for line in out.splitlines():
            if 'LISTENING' not in line:
                continue
            for port in ('8001', '9001'):
                if (':' + port + ' ') in line:
                    listening.add(port)
    except (OSError, subprocess.SubprocessError):
        pass
    value = {'8001': '8001' in listening, '9001': '9001' in listening, '18001': udp_in_use(18001)}
    _PORTS_CACHE['at'], _PORTS_CACHE['value'] = now, value
    return value


# ----------------------------------------------------------------------- accounts
def actor_uid_for(name):
    canonical = name.lower()
    if canonical == 'default':
        return 0x515BB1E1DD242C
    digest = hashlib.sha256(('roe-local-2022:' + canonical).encode('ascii')).digest()
    uid = 0x515BB100000000 | (int.from_bytes(digest[:4], 'big') & 0xFFFFFFFC)
    if uid == 0x515BB1E1DD242C:
        uid ^= 4
    return uid


class Accounts:
    def __init__(self):
        self.path = STATE / 'accounts.json'
        data = read_json(self.path, None)
        if not data:
            data = {'host': 'default', 'accounts': [], 'bindings': {}}
            self._seed_default(data)
            write_json(self.path, data)
        self.data = data
        self.ensure_catalogs()

    def _seed_default(self, data):
        name = 'default'
        data['accounts'].append(dict(
            name=name, actor_uid=actor_uid_for(name),
            cosmetics=self._catalog_path(name),
            state=str(ROOT / 'runtime' / 'local-account' / 'cosmetics-state.json'),
            created=now_iso(), note='内置默认账户',
        ))

    def ensure_catalogs(self):
        for entry in self.data['accounts']:
            path = Path(entry['cosmetics'])
            if path.is_file():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            base = read_json(ROOT / 'config' / 'cosmetics.json', {})
            base['state_file'] = entry.get('state', str(path.parent / 'cosmetics-state.json'))
            write_json(path, base)

    @staticmethod
    def _catalog_path(name):
        if name == 'default':
            return str(ROOT / 'runtime' / 'local-account' / 'catalog.json')
        return str(ROOT / 'runtime' / 'local-accounts' / name / 'catalog.json')

    def list(self):
        return self.data['accounts']

    def get(self, name):
        return next((a for a in self.data['accounts'] if a['name'] == name), None)

    def add(self, name, note=''):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}', name or ''):
            raise ValueError('账户名只能是 1-32 位字母/数字/下划线/短横线，且以字母或数字开头')
        if name.lower() in {'con', 'prn', 'aux', 'nul'}:
            raise ValueError('该名称是 Windows 设备保留名')
        if self.get(name.lower()):
            raise ValueError('账户已存在')
        name = name.lower()
        catalog = Path(self._catalog_path(name))
        catalog.parent.mkdir(parents=True, exist_ok=True)
        base = read_json(ROOT / 'config' / 'cosmetics.json', {})
        base['state_file'] = str(catalog.parent / 'cosmetics-state.json')
        write_json(catalog, base)
        entry = dict(name=name, actor_uid=actor_uid_for(name), cosmetics=str(catalog),
                     state=base['state_file'], created=now_iso(), note=note)
        self.data['accounts'].append(entry)
        write_json(self.path, self.data)
        return entry

    def remove(self, name):
        if name == self.data.get('host'):
            raise ValueError('不能删除当前主机账户')
        entry = self.get(name)
        if not entry:
            raise ValueError('账户不存在')
        self.data['accounts'].remove(entry)
        self.data['bindings'] = {k: v for k, v in self.data['bindings'].items() if v != name}
        write_json(self.path, self.data)
        if name != 'default':
            shutil.rmtree(ROOT / 'runtime' / 'local-accounts' / name, ignore_errors=True)
        return entry

    def bind(self, ip, name):
        if name and not self.get(name):
            raise ValueError('账户不存在')
        if ip:
            self.data['bindings'][ip] = name
        else:
            self.data['bindings'].pop(ip, None)
        write_json(self.path, self.data)

    def set_host(self, name):
        if not self.get(name):
            raise ValueError('账户不存在')
        self.data['host'] = name
        write_json(self.path, self.data)

    def server_file(self):
        payload = {
            'accounts': [dict(name=a['name'], actor_uid=a['actor_uid'], cosmetics=a['cosmetics'])
                         for a in self.data['accounts']],
            'bindings': self.data.get('bindings', {}),
        }
        path = STATE / 'accounts-server.json'
        write_json(path, payload)
        return path


# ----------------------------------------------------------------------- settings
LAUNCH_FIELDS = [
    # key, label, type, default, extra, cli, group, help
    ('kit', '起始套装', 'select', 'glider', ['snowboard', 'glider', 'climb'], '--kit', 'start', '出生时携带的套装：滑翔翼 / 滑雪板 / 攀爬'),
    ('mode', '世界模式', 'select', 'cycle', ['walk', 'cycle'], '--mode', 'start', 'walk=无缩圈计时；cycle=完整单局流程'),
    ('cycle_scale', '缩圈倍率', 'int', 3, {'min': 1, 'max': 10}, '--cycle-scale', 'start', '1=原速（约 32 分钟）；3≈9.5 分钟；10 最快'),
    ('duration', '进程时长(秒)', 'int', 2400, {'min': 120, 'max': 7200}, '--duration', 'start', '含登录/准备的总存活上限，到点会结束整局'),
    ('selection_seconds', '准备时间(秒)', 'int', 47, {'min': 1, 'max': 180}, '--selection-seconds', 'start', '进图前选点/准备界面停留时间，默认 47；调到 8 左右可快速开局'),
    ('start_hour', '地图时间', 'select', 8, [7, 8, 15, 16], '--start-hour', 'world', '地图 16010 允许 7/8/15/16 点'),
    ('temperature_raw', '温度原始值', 'int', 500, {'min': -5000, 'max': 500}, '--temperature-raw', 'world', '0.01°C 单位；500 = 5.0°C（教学值，非原版公式）'),
    ('weapon_profile', '主武器装备', 'select', 'citori', ['citori', 'm4', 'ak47', 'r700', 'mosin', 'usp45'], '--weapon-profile', 'loadout', '起始武器/弹道夹具'),
    ('target', '训练靶', 'select', 'armored', ['none', 'plain', 'armored'], '--target', 'range', '被动靶：普通 / 带护甲'),
    ('practice_targets', '靶数量', 'int', 1, {'min': 1, 'max': 10}, '--practice-targets', 'range', '1-10 个独立 HP/护甲/掉落'),
    ('target_los', '靶遮挡', 'select', 'off', ['off', 'open', 'blocked'], '--target-los', 'range', '需要自备解包地形；默认关'),
    ('vehicle_profile', '载具型号', 'select', 'jeep', ['jeep', 'snowmotor'], '--vehicle-profile', 'range', '训练载具夹具'),
    ('own_armor_absorb_percent', '自身护甲吸收%', 'int', 0, {'min': 0, 'max': 100}, '--own-armor-absorb-percent', 'loadout', '教学数值，0 = 不吸收（非原版）'),
    ('min_own_hp', '最低血量', 'int', 100, {'min': 0, 'max': 1000}, '--min-own-hp', 'loadout', '玩家血量下限：伤害不会把血量打到该值以下；0 = 可以被打死（自动开启零血即死），100 = 默认教学值'),
    ('team_bots', '人机队友', 'int', 2, {'min': 0, 'max': 2}, '--team-bots', 'range', '训练模式自动补充的静止人机队友（队伍上限 3 人）；0 = 关闭；需要训练靶开启'),
    ('frag_damage', '手雷伤害', 'int', 100, {'min': 0, 'max': 1000}, '--frag-damage', 'loadout', '投掷物伤害夹具'),
    ('loot_catalog', '战利品表', 'file', 'config/windows-smoke-20261015.json', None, '--loot-catalog', 'loot', '地面物资 JSON；留空则不生成额外物资'),
    ('bind_host', '监听地址', 'select', '127.0.0.1', ['127.0.0.1', '0.0.0.0'], '--bind-host', 'net', '0.0.0.0 = 允许局域网/N2N 客户端连接'),
    ('advertise_ip', '对外 IP', 'text', '', None, '--advertise-ip', 'net', '写进 JOIN 路由的地址；留空 = 本机'),
    ('client_server', '本机客户端连接', 'text', '127.0.0.1:8001', None, '--client-server', 'net', '本机客户端 -server= 值'),
    ('peer_listing_type', '队友标记字节', 'int', 1, {'min': 0, 'max': 255}, '--peer-listing-type', 'net', '565 列表第 13 字节：0=不标记，1=当前最顺（默认），2=候选试验'),
]
BOOL_FIELDS = [
    ('winter_doors', '可交互门', '--winter-doors', 'world', '1688 扇冬天门；单机档案'),
    ('winter_windows', '可破坏玻璃', '--winter-windows', 'world', '窗户/玻璃破坏确认'),
    ('original_jeeps', '原版吉普', '--original-jeeps', 'world', '原版吉普外观/座位夹具'),
    ('native_airdrop', '原版空投', '--native-airdrop', 'world', '使用解包空投实体（非原版 RNG）'),
    ('native_evacuation', '原版撤离', '--native-evacuation', 'world', '要求缩圈倍率=1'),
    ('reliable_udp', '可靠 UDP', '--reliable-udp', 'debug', 'ACK/重传/重组；官方实现未复刻'),
    ('idle_handoff', '断线续传', '--idle-handoff', 'debug', '需可靠 UDP；保留 live ID 一段时间'),
    ('debug_console', '调试控制台', '--debug-console', 'debug', '写 FileDriven 标记 + Lua 数值探针'),
    ('live_control', '实时指令', '--live-control', 'debug', '面板注入回血/补弹/击杀等动作'),
    ('death_on_zero', '零血即死', '--death-on-zero', 'debug', '血量归零立即 0x533，而不是倒地流程'),
    ('validate_movement', '移动校验', '--validate-movement', 'debug', '服务端移动预算校验（默认关）'),
    ('coop', '双人联机（场景同步）', '--coop', 'net', '开启后场景同步其他玩家；会关闭门/可破坏物与自定义战利品表'),
    ('coop_team_sync', '强制共享队伍（实验）', '--coop-team-sync', 'net', '服务端伪造队伍报文；可能让大厅 UI 异常（出现 [object Object] / 无法准备），默认关'),
    ('diagnostic_hazard', '教学危险区', '--diagnostic-hazard', 'debug', '撤离绳附近的隐形伤害矩形'),
    ('diagnostic_departure', '诊断离场', '--diagnostic-departure', 'debug', '诊断用载具离场'),
    ('vehicle_damage_practice', '载具伤害教学', '--vehicle-damage-practice', 'debug', '每发 500 HP 的教学值'),
    ('bots', '诊断机器人', '--bots', 'range', '无 AI，仅走路/开枪夹具'),
    ('bot_ground_route', '机器人寻路', '--bot-ground-route', 'range', '需要诊断机器人'),
    ('bot_behavior', '机器人行为', '--bot-behavior', 'range', '需要机器人 + 寻路 + cycle'),
    ('climb_practice', '攀爬练习', '--climb-practice', 'range', '需要套装=攀爬、模式=walk'),
    ('boat_practice', '船只练习', '--boat-practice', 'range', '固定起点在船上'),
]
GROUPS = [
    ('start', '启动 / 剧本'), ('world', '世界与时间'), ('loadout', '武器与装备'),
    ('loot', '战利品'), ('range', '靶场 / 机器人'), ('net', '联网'), ('debug', '调试与实验'),
]
DEFAULTS = {f[0]: f[3] for f in LAUNCH_FIELDS}
DEFAULTS.update({f[0]: False for f in BOOL_FIELDS})


class Settings:
    def __init__(self):
        self.path = STATE / 'settings.json'
        self.values = dict(DEFAULTS)
        self.values.update(read_json(self.path, {}))

    def save(self, patch):
        for key, value in patch.items():
            if key in DEFAULTS:
                self.values[key] = self._coerce(key, value)
        write_json(self.path, self.values)
        return self.values

    def _coerce(self, key, value):
        field = next((f for f in LAUNCH_FIELDS if f[0] == key), None)
        if field:
            kind, default, extra = field[2], field[3], field[4]
            if kind == 'int':
                value = int(value)
                if 'min' in (extra or {}):
                    value = max(extra['min'], min(extra['max'], value))
            elif kind == 'select':
                if value not in extra:
                    raise ValueError(f'{key} 取值非法')
            return value
        return bool(value)

    def schema(self):
        out = []
        for key, label, kind, default, extra, cli, group, help_text in LAUNCH_FIELDS:
            out.append(dict(key=key, label=label, type=kind, default=default, options=extra,
                            cli=cli, group=group, help=help_text, value=self.values[key]))
        for key, label, cli, group, help_text in BOOL_FIELDS:
            out.append(dict(key=key, label=label, type='bool', default=False, options=None,
                            cli=cli, group=group, help=help_text, value=self.values[key]))
        return dict(groups=[dict(id=i, title=t) for i, t in GROUPS], fields=out)

    def server_args(self, client, host_profile, accounts_file, host_only):
        cmd = [str(PY), '-X', 'utf8', '-B', '-u', str(LAUNCH),
               '--client', str(client), '--dotnet', str(DOTNET),
               '--profile', host_profile,
               '--bind-host', str(self.values['bind_host']),
               '--client-server', str(self.values['client_server'])]
        if self.values.get('advertise_ip'):
            cmd += ['--advertise-ip', str(self.values['advertise_ip'])]
        if accounts_file:
            cmd += ['--accounts-file', str(accounts_file)]
        if host_only:
            cmd += ['--no-client']
        for key, label, kind, default, extra, cli, group, help_text in LAUNCH_FIELDS:
            if key in ('bind_host', 'client_server'):
                continue
            value = self.values.get(key)
            if key == 'advertise_ip':
                continue
            if kind == 'bool':
                continue
            if value is None or value == '':
                continue
            if key == 'loot_catalog':
                if self.values.get('coop'):
                    continue
                path = Path(value)
                if not path.is_absolute():
                    path = ROOT / path
                if not path.is_file():
                    continue
                value = str(path)
            cmd += [cli, str(value)]
        if self.values.get('min_own_hp') == 0 and not self.values.get('death_on_zero'):
            cmd.append('--death-on-zero')
        for key, label, cli, group, help_text in BOOL_FIELDS:
            if self.values.get(key):
                cmd.append(cli)
        return cmd


# ---------------------------------------------------------------------- processes
class Server:
    def __init__(self):
        self.proc = None
        self.log_path = None
        self.started = None
        self.run_dir = None
        self.lock = threading.Lock()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd, label):
        with self.lock:
            if self.running():
                raise ValueError('服务端已在运行')
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            self.log_path = LOGS / f'server-{ts}.log'
            handle = self.log_path.open('w', encoding='utf-8', buffering=1)
            env = dict(os.environ)
            env['ROE_SKIP_FIREWALL'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            self.proc = subprocess.Popen(
                cmd, cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT,
                env=env, creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
            self.started = time.time()
            self.run_dir = None
            return dict(pid=self.proc.pid, log=str(self.log_path), cmd=cmd, label=label)

    def stop(self):
        with self.lock:
            if not self.running():
                self.proc = None
                return dict(stopped=False, reason='未运行')
            pid = self.proc.pid
            try:
                self.proc.send_signal(getattr(__import__('signal'), 'CTRL_BREAK_EVENT'))
            except (OSError, ValueError):
                pass
            deadline = time.time() + 8
            while time.time() < deadline and self.proc.poll() is None:
                time.sleep(0.25)
            if self.proc.poll() is None:
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                               capture_output=True, creationflags=CREATE_NO_WINDOW)
            self.proc = None
            return dict(stopped=True, pid=pid)

    def newest_run(self):
        if not RUNS.is_dir():
            return None
        since = (self.started or 0) - 5
        dirs = [d for d in RUNS.iterdir() if d.is_dir() and d.stat().st_mtime >= since]
        return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None

    def status(self):
        alive = self.running()
        run = self.newest_run()
        info = dict(running=alive, pid=self.proc.pid if self.proc else None,
                    uptime=int(time.time() - self.started) if alive and self.started else 0,
                    log=str(self.log_path) if self.log_path else None,
                    ports=listen_ports(), run=str(run) if run else None)
        if run:
            info['run'] = str(run)
            info['ready'] = {
                'lobby': log_has(run / 'lobby.log', 'Started on port 9001'),
                'proxy': log_has(run / 'proxy.log', '"kind": "ready"'),
                'endpoint': log_has(run / 'endpoint.log', '"kind": "ready"'),
            }
            info['events'] = count_events(run)
            if not alive:
                info['ready'] = {key: False for key in info['ready']}
        return info


def log_has(path, needle):
    try:
        with Path(path).open('rb') as fh:
            head = fh.read(128 * 1024)
    except OSError:
        return False
    return needle in head.decode('utf-8', 'ignore')


_PLAYERS_CACHE = {}


def live_players(run):
    """Online players of the current run, parsed from the lobby proxy log."""
    path = Path(run) / 'proxy.log'
    if not path.is_file():
        return []
    stat = path.stat()
    key = (str(path), stat.st_mtime, stat.st_size)
    cached = _PLAYERS_CACHE.get('value')
    if cached and cached[0] == key:
        return cached[1]
    online, assigned = {}, {}
    try:
        with path.open(encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if '"account_assigned"' in line:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    rec = dict(uid=row.get('actor_uid'), name=row.get('profile'),
                               remote=row.get('remote'), connection=row.get('connection'))
                    if rec['uid']:
                        assigned[row.get('connection')] = rec
                        online[row.get('connection')] = rec
                elif '"kind": "disconnect"' in line:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    online.pop(row.get('connection'), None)
    except OSError:
        return []
    rows = list((online or assigned).values())
    _PLAYERS_CACHE['value'] = (key, rows)
    return rows


def live_results(run):
    """Last applied/rejected admin actions from endpoint.log."""
    path = Path(run) / 'endpoint.log'
    if not path.is_file():
        return []
    out = []
    try:
        with path.open(encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if '"live_state_action"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                out.append(dict(time=row.get('timestamp', '')[11:19], action=row.get('action'),
                                accepted=row.get('accepted'), reason=row.get('reason'),
                                hp=row.get('hp'), definition=row.get('definition'),
                                quantity=row.get('quantity'), id=row.get('id')))
                if len(out) > 200:
                    out = out[-100:]
    except OSError:
        return []
    return out[-10:]


def count_events(run):
    out = {}
    for name in ('endpoint', 'lobby', 'proxy'):
        p = run / f'{name}.log'
        if not p.is_file():
            continue
        kinds = {}
        try:
            with p.open(encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    if '"kind"' not in line:
                        continue
                    try:
                        k = json.loads(line).get('kind')
                    except ValueError:
                        continue
                    kinds[k] = kinds.get(k, 0) + 1
        except OSError:
            continue
        out[name] = kinds
    return out


def bring_window_to_front(pid, attempts=3, delay=6.0):
    """游戏窗口如果在后台，引擎会暂缓初始化/联网；启动后主动拉到前台。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    for _ in range(attempts):
        time.sleep(delay)
        found = []
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length:
                    found.append(hwnd)
            return True

        user32.EnumWindows(proc(callback), 0)
        if found:
            hwnd = found[0]
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            return True
    return False


class Clients:
    def __init__(self):
        self.items = []
        self.lock = threading.Lock()

    def launch(self, client_dir, server_ip, port, account_hint=''):
        exe = Path(client_dir) / 'Europa_Client.exe'
        if not exe.is_file():
            raise ValueError('客户端目录里没有 Europa_Client.exe')
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        log = LOGS / f'client-{ts}-{len(self.items) + 1}.log'
        handle = log.open('w', encoding='utf-8', buffering=1)
        proc = subprocess.Popen(
            [str(exe), '-language=en', '-garena', '-uid=1', f'-server={server_ip}:{port}'],
            cwd=str(client_dir), stdout=handle, stderr=subprocess.STDOUT,
            creationflags=CREATE_NEW_PROCESS_GROUP)
        with self.lock:
            self.items.append(dict(pid=proc.pid, server=f'{server_ip}:{port}', started=now_iso(),
                                   log=str(log), account=account_hint, proc=proc))
        threading.Thread(target=bring_window_to_front, args=(proc.pid,), daemon=True).start()
        return dict(pid=proc.pid, log=str(log))

    def list(self):
        with self.lock:
            for item in self.items:
                item['running'] = item['proc'].poll() is None
            return [{k: v for k, v in i.items() if k != 'proc'} for i in self.items]

    def stop(self, pid=None):
        stopped = []
        with self.lock:
            for item in self.items:
                if item['proc'].poll() is not None:
                    continue
                if pid and item['pid'] != pid:
                    continue
                try:
                    subprocess.run(['taskkill', '/PID', str(item['pid']), '/T', '/F'],
                                   capture_output=True, creationflags=CREATE_NO_WINDOW)
                    stopped.append(item['pid'])
                except OSError:
                    pass
        return stopped


# -------------------------------------------------------------------------- rooms
class Rooms:
    def __init__(self):
        self.path = STATE / 'rooms.json'
        self.data = read_json(self.path, {'rooms': []})

    def list(self):
        return self.data['rooms']

    def create(self, name, host, mode='cycle', map_id=16010, maximum=4, note=''):
        room = dict(id='r' + datetime.now().strftime('%H%M%S'), name=name.strip()[:40] or '未命名房间',
                    host=host, mode=mode, map=map_id, max=int(maximum), members=[host],
                    status='open', created=now_iso(), note=note)
        self.data['rooms'].append(room)
        write_json(self.path, self.data)
        return room

    def update(self, room_id, action, account=None):
        room = next((r for r in self.data['rooms'] if r['id'] == room_id), None)
        if not room:
            raise ValueError('房间不存在')
        if action == 'join' and account and account not in room['members']:
            if len(room['members']) >= room['max']:
                raise ValueError('房间已满')
            room['members'].append(account)
        elif action == 'leave' and account in room['members']:
            room['members'].remove(account)
        elif action == 'start':
            room['status'] = 'starting'
            room['started_at'] = now_iso()
        elif action == 'reset':
            room['status'] = 'open'
        elif action == 'delete':
            self.data['rooms'].remove(room)
            write_json(self.path, self.data)
            return {'deleted': room_id}
        write_json(self.path, self.data)
        return room


# ------------------------------------------------------------------------ configs
def config_files():
    out = []
    for path in sorted((ROOT / 'config').glob('*.json')):
        stat = path.stat()
        out.append(dict(name=path.stem, file=str(path), size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                        read_only=path.stem in ('wire', 'region-source')))
    return out


def read_config(name):
    path = ROOT / 'config' / (name + '.json')
    if not path.is_file():
        raise ValueError('配置不存在')
    return path.read_text(encoding='utf-8')


def write_config(name, text):
    path = ROOT / 'config' / (name + '.json')
    if not path.is_file():
        raise ValueError('配置不存在')
    if name in ('wire', 'region-source'):
        raise ValueError('该文件为只读夹具索引')
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise ValueError(f'JSON 语法错误: {exc}')
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(path, BACKUPS / f'{name}-{ts}.json')
    write_json(path, parsed)
    return dict(name=name, bytes=len(text))


# --------------------------------------------------------------------------- HTTP
class App:
    def __init__(self):
        self.accounts = Accounts()
        self.settings = Settings()
        self.server = Server()
        self.clients = Clients()
        self.rooms = Rooms()
        self.client_dir = self._detect_client()

    def _detect_client(self):
        stored = read_json(STATE / 'client.json', {})
        if stored.get('path') and (Path(stored['path']) / 'Europa_Client.exe').is_file():
            return Path(stored['path'])
        if DEFAULT_CLIENT.is_dir():
            return DEFAULT_CLIENT
        return Path('')

    def set_client(self, path):
        path = Path(path)
        if not (path / 'Europa_Client.exe').is_file():
            raise ValueError('该目录下没有 Europa_Client.exe')
        self.client_dir = path
        write_json(STATE / 'client.json', {'path': str(path)})

    def start_server(self, host_only=False):
        if not self.client_dir or not (Path(self.client_dir) / 'Europa_Client.exe').is_file():
            raise ValueError('请先设置客户端目录')
        accounts_file = self.accounts.server_file()
        cmd = self.settings.server_args(self.client_dir, self.accounts.data['host'], accounts_file, True)
        info = self.server.start(cmd, 'host' if host_only else 'single')
        if not host_only:
            threading.Thread(target=self._launch_local_client_when_ready, daemon=True).start()
        return info

    def _launch_local_client_when_ready(self):
        for _ in range(120):
            if not self.server.running():
                return
            if port_open(8001):
                time.sleep(1.0)
                try:
                    self.clients.launch(self.client_dir, '127.0.0.1', 8001)
                except OSError:
                    pass
                return
            time.sleep(0.5)

    # ------------------------------------------------------------- live control
    def start_coop(self, ip, with_client=True):
        if not ip:
            raise ValueError('请选择或填写对外 IP（局域网或 N2N 地址）')
        self.settings.save({'bind_host': '0.0.0.0', 'advertise_ip': ip, 'team_bots': 0, 'coop': True})
        if len(self.accounts.list()) < 2:
            self.accounts.add('friend', '双人联机自动创建')
        info = self.start_server(host_only=not with_client)
        info['join'] = '-language=en -garena -uid=1 -server=%s:8001' % ip
        info['ip'] = ip
        return info

    def live_status(self):
        run = self.server.newest_run()
        out = dict(enabled=bool(self.settings.values.get('live_control')),
                   running=self.server.running(),
                   run=str(run) if run else None, queue=[], results=[])
        if run:
            path = run / 'live-commands.json'
            if path.is_file():
                try:
                    out['queue'] = json.loads(path.read_text(encoding='utf-8-sig'))[-20:]
                except ValueError:
                    out['queue'] = []
            out['results'] = live_results(run)
            out['players'] = live_players(run)
        return out

    def live_action(self, body):
        if not self.settings.values.get('live_control'):
            raise ValueError('实时指令未启用：在「服务器」页勾选「实时指令」并重启服务端')
        run = self.server.newest_run()
        if run is None:
            raise ValueError('还没有运行记录，先开一局')
        path = run / 'live-commands.json'
        rows = []
        if path.is_file():
            rows = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(rows, list):
                raise ValueError('live-commands.json 格式不对')
        action = body.get('action')
        row = dict(id='ui-' + uuid.uuid4().hex[:8], action=action)
        for key in ('hp', 'quantity', 'definition', 'damage'):
            if body.get(key) not in (None, ''):
                row[key] = int(body[key])
        if body.get('npc_uid'):
            row['npc_uid'] = str(body['npc_uid'])
        if body.get('recipient'):
            row['recipient_actor_uid'] = str(body['recipient'])
        if str(ROOT / 'server' / 'directory') not in sys.path:
            sys.path.insert(0, str(ROOT / 'server' / 'directory'))
        from state_scene_actions_2022 import validate_state_action
        validate_state_action(row)
        if len(rows) >= 128:
            raise ValueError('队列已满（128 条），重启服务端可清空')
        rows.append(row)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)
        return dict(id=row['id'], queued=len(rows))

    def status(self):
        return dict(
            server=self.server.status(),
            clients=self.clients.list(),
            settings=self.settings.values,
            client_dir=str(self.client_dir),
            ips=local_ips(),
            accounts=self.accounts.list(),
            host_account=self.accounts.data.get('host'),
            bindings=self.accounts.data.get('bindings', {}),
            rooms=self.rooms.list(),
        )


APP = App()


class Handler(BaseHTTPRequestHandler):
    server_version = 'ROEControl/1.0'

    def log_message(self, fmt, *args):
        pass

    # -- helpers
    def _send(self, code, payload=None, content_type='application/json', raw=None):
        body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionError, OSError):
            pass

    def _json_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode('utf-8'))

    # -- routing
    def do_GET(self):
        try:
            self._route('GET')
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self._send(500, {'error': str(exc)})

    def do_POST(self):
        try:
            self._route('POST')
        except ValueError as exc:
            self._send(400, {'error': str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {'error': str(exc)})

    def do_DELETE(self):
        try:
            self._route('DELETE')
        except ValueError as exc:
            self._send(400, {'error': str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {'error': str(exc)})

    def _route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == '/' or path.startswith('/web/'):
            return self._static(path)
        if path == '/api/status' and method == 'GET':
            return self._send(200, APP.status())
        if path == '/api/settings' and method == 'GET':
            return self._send(200, dict(schema=APP.settings.schema(), values=APP.settings.values))
        if path == '/api/settings' and method == 'POST':
            values = APP.settings.save(self._json_body().get('values', {}))
            return self._send(200, dict(values=values))

        if path == '/api/accounts' and method == 'GET':
            return self._send(200, dict(accounts=APP.accounts.list(),
                                        bindings=APP.accounts.data.get('bindings', {}),
                                        host=APP.accounts.data.get('host')))
        if path == '/api/accounts' and method == 'POST':
            body = self._json_body()
            return self._send(200, APP.accounts.add(body.get('name', ''), body.get('note', '')))
        if path.startswith('/api/accounts/') and method == 'DELETE':
            name = path.rsplit('/', 1)[-1]
            return self._send(200, APP.accounts.remove(name))
        if path == '/api/accounts/bind' and method == 'POST':
            body = self._json_body()
            APP.accounts.bind(body.get('ip', ''), body.get('name', ''))
            return self._send(200, dict(bindings=APP.accounts.data.get('bindings', {})))
        if path == '/api/accounts/host' and method == 'POST':
            APP.accounts.set_host(self._json_body().get('name', ''))
            return self._send(200, dict(host=APP.accounts.data.get('host')))

        if path == '/api/server/start' and method == 'POST':
            body = self._json_body()
            return self._send(200, APP.start_server(host_only=bool(body.get('host_only'))))
        if path == '/api/server/stop' and method == 'POST':
            result = APP.server.stop()
            result['clients'] = APP.clients.stop()
            return self._send(200, result)
        if path == '/api/server/preview' and method == 'GET':
            accounts_file = APP.accounts.server_file()
            cmd = APP.settings.server_args(APP.client_dir, APP.accounts.data['host'], accounts_file, False)
            return self._send(200, dict(cmd=cmd, line=subprocess.list2cmdline(cmd)))

        if path == '/api/client/launch' and method == 'POST':
            body = self._json_body()
            ip = body.get('ip') or '127.0.0.1'
            port = int(body.get('port') or 8001)
            return self._send(200, APP.clients.launch(APP.client_dir, ip, port, body.get('account', '')))
        if path == '/api/client/stop' and method == 'POST':
            body = self._json_body()
            return self._send(200, dict(stopped=APP.clients.stop(body.get('pid'))))
        if path == '/api/client/preview' and method == 'GET':
            ip = query.get('ip', ['127.0.0.1'])[0]
            port = query.get('port', ['8001'])[0]
            line = subprocess.list2cmdline([str(Path(APP.client_dir) / 'Europa_Client.exe'),
                                            '-language=en', '-garena', '-uid=1', f'-server={ip}:{port}'])
            return self._send(200, dict(line=line))

        if path == '/api/rooms' and method == 'GET':
            return self._send(200, dict(rooms=APP.rooms.list()))
        if path == '/api/rooms' and method == 'POST':
            body = self._json_body()
            return self._send(200, APP.rooms.create(body.get('name', ''), body.get('host', ''),
                                                    body.get('mode', 'cycle'), body.get('map', 16010),
                                                    body.get('max', 4), body.get('note', '')))
        if path.startswith('/api/rooms/') and method == 'POST':
            parts = path.strip('/').split('/')
            room_id, action = parts[2], parts[3] if len(parts) > 3 else ''
            body = self._json_body()
            return self._send(200, APP.rooms.update(room_id, action, body.get('account')))
        if path.startswith('/api/rooms/') and method == 'DELETE':
            return self._send(200, APP.rooms.update(path.rsplit('/', 1)[-1], 'delete'))

        if path == '/api/configs' and method == 'GET':
            return self._send(200, dict(configs=config_files()))
        if path.startswith('/api/configs/') and method == 'GET':
            return self._send(200, dict(text=read_config(path.rsplit('/', 1)[-1])))
        if path.startswith('/api/configs/') and method == 'POST':
            return self._send(200, write_config(path.rsplit('/', 1)[-1], self._json_body().get('text', '')))

        if path == '/api/logs' and method == 'GET':
            return self._send(200, dict(logs=self._log_list()))
        if path == '/api/logs/tail' and method == 'GET':
            target = query.get('path', [''])[0]
            n = int(query.get('n', ['200'])[0])
            return self._send(200, dict(lines=self._tail(target, n)))

        if path == '/api/coop/start' and method == 'POST':
            body = self._json_body()
            return self._send(200, APP.start_coop(body.get('ip', ''), bool(body.get('with_client', True))))
        if path == '/api/coop/stop' and method == 'POST':
            result = APP.server.stop()
            result['clients'] = APP.clients.stop()
            return self._send(200, result)
        if path == '/api/live/status' and method == 'GET':
            return self._send(200, APP.live_status())
        if path == '/api/live/action' and method == 'POST':
            return self._send(200, APP.live_action(self._json_body()))

        if path == '/api/client/dir' and method == 'POST':
            APP.set_client(self._json_body().get('path', ''))
            return self._send(200, dict(path=str(APP.client_dir)))

        return self._send(404, {'error': 'not found'})

    # -- static / logs
    def _static(self, path):
        rel = 'index.html' if path == '/' else path.replace('/web/', '', 1)
        target = (WEB / rel).resolve()
        if not str(target).startswith(str(WEB.resolve())) or not target.is_file():
            return self._send(404, {'error': 'not found'})
        ctype = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
                 '.png': 'image/png', '.svg': 'image/svg+xml'}.get(target.suffix, 'text/plain')
        return self._send(200, content_type=ctype, raw=target.read_bytes())

    def _log_list(self):
        out = []
        for path in sorted(LOGS.glob('*.log'), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
            out.append(dict(name=path.name, path=str(path), size=path.stat().st_size,
                            modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')))
        if RUNS.is_dir():
            for run in sorted((d for d in RUNS.iterdir() if d.is_dir()),
                              key=lambda d: d.stat().st_mtime, reverse=True)[:10]:
                for name in ('endpoint.log', 'proxy.log', 'lobby.log', 'client.log'):
                    p = run / name
                    if p.is_file():
                        out.append(dict(name=f'{run.name}/{name}', path=str(p), size=p.stat().st_size,
                                        modified=datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds')))
        return out

    def _tail(self, target, n):
        path = Path(target).resolve()
        allowed = str(path).startswith(str(LOGS.resolve())) or str(path).startswith(str(RUNS.resolve()))
        if not allowed or not path.is_file():
            raise ValueError('日志路径不允许')
        with path.open('rb') as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 256 * 1024))
            data = fh.read().decode('utf-8', errors='replace').splitlines()
        return data[-n:]


def main():
    host = '127.0.0.1'
    app_server = ThreadingHTTPServer((host, APP_PORT), Handler)
    url = f'http://{host}:{APP_PORT}/'
    print(f'ROE control panel: {url}', flush=True)
    print(f'root={ROOT}', flush=True)
    print(f'client={APP.client_dir}', flush=True)
    if '--no-browser' not in sys.argv:
        edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
        try:
            if edge.is_file():
                subprocess.Popen([str(edge), f'--app={url}', '--window-size=1500,950'],
                                 creationflags=CREATE_NO_WINDOW)
            else:
                webbrowser.open(url)
        except OSError:
            webbrowser.open(url)
    try:
        app_server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
