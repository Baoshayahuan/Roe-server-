# -*- coding: utf-8 -*-
"""Sanitize machine-specific paths before publishing."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

# 1. build artefacts of the C# lobby are rebuilt by the launcher
for sub in ('server/lobby/LobbyEmulator.Sdk/bin', 'server/lobby/LobbyEmulator.Sdk/obj'):
    shutil.rmtree(ROOT / sub, ignore_errors=True)

# 2. panel: no hardcoded personal client path
app = ROOT / 'control' / 'app.py'
text = app.read_text(encoding='utf-8')
text = text.replace(
    "DEFAULT_CLIENT = Path(r'H:\\st\\steamapps\\common\\Ring of Elysium')",
    "DEFAULT_CLIENT = Path(os.environ.get('ROE_CLIENT', ''))")
app.write_text(text, encoding='utf-8')

# 3. local launcher: take the client path from the command line or ask
start = ROOT / 'Start-Local.cmd'
if start.is_file():
    start.write_text(
        '@echo off\r\n'
        'rem Local one-click launcher (Windows). Usage: Start-Local.cmd "D:\\path\\to\\Ring of Elysium"\r\n'
        'setlocal\r\n'
        'if "%~1"=="" (\r\n'
        '  echo Usage: Start-Local.cmd "path to Ring of Elysium"\r\n'
        '  exit /b 2\r\n'
        ')\r\n'
        'set "ROE_SKIP_FIREWALL=1"\r\n'
        'call "%~dp0run-roe-2022.cmd" -Client "%~1" -Kit glider -Mode cycle -CycleScale 3 -Duration 2400 '
        '-ReliableUDP -IdleHandoff -WinterDoors -WinterWindows -DebugConsole -Target armored '
        '-LootCatalog "%~dp0config\\windows-smoke-20261015.json"\r\n'
        'exit /b %ERRORLEVEL%\r\n', encoding='ascii')

# 4. local install notes: strip the personal path
note = ROOT / 'INSTALL-LOCAL.md'
if note.is_file():
    data = note.read_text(encoding='utf-8')
    data = data.replace('H:\\st\\steamapps\\common\\Ring of Elysium', '<你的客户端目录>')
    note.write_text(data, encoding='utf-8')

print('sanitized')
