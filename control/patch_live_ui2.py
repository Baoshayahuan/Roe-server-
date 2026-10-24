# -*- coding: utf-8 -*-
"""Frontend: player selector for live actions + correct result rendering."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'control' / 'web' / 'index.html'
JS = ROOT / 'control' / 'web' / 'app.js'
changed = []

html = HTML.read_text(encoding='utf-8')
old = '          <div class="muted" id="live-state">读取中…</div>'
new = ('          <div class="row">\n'
       '            <span class="muted">目标玩家</span>\n'
       '            <select id="live-player"></select>\n'
       '            <span class="muted" id="live-state">读取中…</span>\n'
       '          </div>')
if new in html:
    changed.append('skip html')
else:
    if old not in html:
        raise SystemExit('html anchor missing')
    HTML.write_text(html.replace(old, new, 1), encoding='utf-8')
    changed.append('patch html')

js = JS.read_text(encoding='utf-8')

old_players = """    const results = document.getElementById('live-results');"""
new_players = """    const sel = document.getElementById('live-player');
    if (sel) {
      const cur = sel.value;
      sel.innerHTML = '';
      sel.appendChild(h('option', { value: '' }, '全部 / 默认'));
      for (const p of (d.players || [])) {
        sel.appendChild(h('option', { value: p.uid }, `${p.name || '?'} · ${p.remote || ''}`));
      }
      if (cur) sel.value = cur;
    }
    const results = document.getElementById('live-results');"""
if new_players not in js:
    if old_players not in js:
        raise SystemExit('players anchor missing')
    js = js.replace(old_players, new_players, 1)
    changed.append('patch js.players')

old_null = """          `${r.time || ''}  ${r.action}  `,
          h('span', { style: `color:${ok ? '#8ce99a' : '#ffb4ae'}` }, ok ? '已执行' : (r.reason || '拒绝')),
          r.hp !== undefined ? `  hp=${r.hp}` : '',
          r.definition !== undefined ? `  ${r.definition} +${r.quantity}` : ''));"""
new_null = """          `${r.time || ''}  ${r.action}  `,
          h('span', { style: `color:${ok ? '#8ce99a' : '#ffb4ae'}` }, ok ? '已执行' : (r.reason || '拒绝')),
          r.hp != null ? `  hp=${r.hp}` : '',
          r.definition != null && r.quantity != null ? `  ${r.definition} +${r.quantity}` : ''));"""
if new_null not in js:
    if old_null not in js:
        raise SystemExit('null anchor missing')
    js = js.replace(old_null, new_null, 1)
    changed.append('patch js.null')

old_action = """async function liveAction(payload) {
  try {
    const r = await api('/api/live/action', { method: 'POST', body: payload });"""
new_action = """async function liveAction(payload) {
  const sel = document.getElementById('live-player');
  if (sel && sel.value) payload.recipient = sel.value;
  try {
    const r = await api('/api/live/action', { method: 'POST', body: payload });"""
if new_action not in js:
    if old_action not in js:
        raise SystemExit('action anchor missing')
    js = js.replace(old_action, new_action, 1)
    changed.append('patch js.action')

JS.write_text(js, encoding='utf-8')
print('\n'.join(changed))
