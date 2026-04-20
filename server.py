#!/usr/bin/env python3
"""
TikTok LIVE · AI Insight · Phase-1 mock backend.

Zero-dep Python stdlib server. Serves:
  /                 → mobile-demo.html
  /dashboard        → dashboard.html (ops view)
  /*.mp4 /*.jpg     → static clip assets
  /api/sessions/*   → session events from the demo
  /api/messages/*   → message-level feedback events
  /api/admin/*      → dashboard-facing (events / metrics / killswitch / reset)

Persists events to a local SQLite file so a page reload doesn't lose state.
"""

import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, 'aiinsight.db')
PORT = int(os.environ.get('PORT', 8765))

# Killswitch lives in-memory (PRD §3.3 Layer 8 · 30s SLA).
# Toggled from the dashboard; affects session.open responses so the mobile
# demo can render a degraded banner when ops "pulls the cord".
KILLSWITCH = {'active': False, 'reason': ''}

# ──────────────────────────────────────────────────────────────────
# Editable template store (dashboard "Templates" tab writes here,
# mobile demo fetches on boot + on openChat). Keys are dot-paths;
# demo has a small lookup table mapping each key into its consumer.
# Keep this list tight — every new key = another editor row.
# ──────────────────────────────────────────────────────────────────
TEMPLATE_SEEDS = {
    # Proactive AI Insight (Violation Page opener · streamed at 25 ms/char)
    'proactiveAI.v_001':
        'At 12:34:56 the system flagged revealing clothing combined with body-focused framing — '
        'that combination matches our Sexually Suggestive Content policy. Gifting is suspended and '
        'reach is limited until 4/20.',
    'proactiveAI.v_002':
        'At 13:14 the system flagged visible currency on-screen plus solicitation gestures — that '
        'pattern matched our Inorganic Gift Solicitation policy. Reach is limited until 4/20. '
        'Gifting is unaffected.',
    'proactiveAI.v_003':
        'At 13:42 the system again detected currency-on-screen plus pleading gestures — same '
        'Inorganic Gift Solicitation pattern as the earlier flag at 13:14. Reach limit extended.',

    # Chat responses · Inorganic Gift Solicitation (policy.id = inorganic_gift_solicitation)
    'chat.inorganic_gift_solicitation.understand':
        'Your LIVE was flagged because the system detected <strong>signs requesting money and '
        'solicitation gestures</strong> directed at viewers. That pattern violates our Integrity '
        'and Authenticity guidelines.',
    'chat.inorganic_gift_solicitation.improve':
        'Here\'s how to stay compliant:\n\n'
        '• Do not display signs requesting money, gifts, or donations\n'
        '• Avoid simulating or performing solicitation as content\n'
        '• Don\'t use sympathy tactics ("I need this to survive") to encourage gifting\n'
        '• Focus on authentic, engaging content that showcases your talent',
    'chat.inorganic_gift_solicitation.nextSteps':
        'This restriction is active from <strong>4/13/2026 10:00 AM</strong> to '
        '<strong>4/20/2026 10:00 AM</strong>. It lifts automatically.\n\n'
        'Gifting is unaffected — viewers can still gift voluntarily. Only recommendation reach '
        'is limited. You can file an appeal before the restriction ends.',

    # Chat responses · Sexually Suggestive Content (policy.id = body_exposure)
    'chat.body_exposure.understand':
        'Your LIVE was flagged because the system detected <strong>revealing clothing combined '
        'with body-focused framing</strong> in the clip. That combination matches the pattern for '
        'sexually suggestive content under our Sexually Suggestive Content policy.',
    'chat.body_exposure.improve':
        'Here\'s how to stay compliant:\n\n'
        '• Avoid low-cut, sheer, or tight revealing outfits as your main LIVE wardrobe\n'
        '• Keep camera framing on your activity or face — not on your body\n'
        '• For fitness/dance content, wear sport-appropriate coverage\n'
        '• Avoid suggestive poses, hip/chest focus, and slow body pans',
    'chat.body_exposure.nextSteps':
        'This restriction is active from <strong>4/13/2026 10:00 AM</strong> to '
        '<strong>4/20/2026 10:00 AM</strong>. It lifts automatically — you don\'t need to do '
        'anything.\n\n'
        'You can file an appeal at any time before the restriction ends. Non-LIVE content '
        '(videos, posts) is unaffected.',
}

# Human-readable metadata for the dashboard editor — keep order + group labels
TEMPLATE_META = [
    {'group': 'Proactive AI Insight · Violation Page', 'keys': [
        ('proactiveAI.v_001', 'V1 · body_exposure · Evening Stream 💃 12:34 PM'),
        ('proactiveAI.v_002', 'V2 · inorganic_gift_solicitation · 1:14 PM'),
        ('proactiveAI.v_003', 'V3 · inorganic_gift_solicitation · 1:42 PM (repeat)'),
    ]},
    {'group': 'Chat · Inorganic Gift Solicitation', 'keys': [
        ('chat.inorganic_gift_solicitation.understand', 'intent: 💡 Why was my LIVE flagged?'),
        ('chat.inorganic_gift_solicitation.improve',    'intent: 📚 How do I avoid this next time?'),
        ('chat.inorganic_gift_solicitation.nextSteps',  'intent: ⏱️ What happens now?'),
    ]},
    {'group': 'Chat · Sexually Suggestive Content', 'keys': [
        ('chat.body_exposure.understand', 'intent: 💡 Why was my LIVE flagged?'),
        ('chat.body_exposure.improve',    'intent: 📚 How do I avoid this next time?'),
        ('chat.body_exposure.nextSteps',  'intent: ⏱️ What happens now?'),
    ]},
]

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.mp4':  'video/mp4',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                ai_session_id TEXT,
                violation_id TEXT,
                payload TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
            CREATE INDEX IF NOT EXISTS idx_events_sess ON events(ai_session_id);

            CREATE TABLE IF NOT EXISTS templates (
                key              TEXT PRIMARY KEY,
                content          TEXT NOT NULL,
                default_content  TEXT NOT NULL,
                updated_at       REAL NOT NULL
            );
        ''')
        # Seed / re-seed defaults. Preserves any custom `content` the user edited.
        now = time.time()
        for key, default in TEMPLATE_SEEDS.items():
            conn.execute('''
                INSERT INTO templates (key, content, default_content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET default_content = excluded.default_content
            ''', (key, default, default, now))
        conn.commit()


def log_event(kind, ai_session_id=None, violation_id=None, payload=None):
    with connect() as conn:
        cur = conn.execute(
            'INSERT INTO events (ts, kind, ai_session_id, violation_id, payload) VALUES (?, ?, ?, ?, ?)',
            (time.time(), kind, ai_session_id, violation_id, json.dumps(payload or {}))
        )
        conn.commit()
        return cur.lastrowid


class Handler(BaseHTTPRequestHandler):
    # Silence default stdout logging — noisy otherwise
    def log_message(self, fmt, *args):
        return

    # ── helpers ────────────────────────────────────────────────────
    def _send_json(self, code, obj):
        body = json.dumps(obj, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode('utf-8') or '{}')
        except Exception:
            return {}

    def _serve_static(self, rel_path):
        safe = rel_path.lstrip('/')
        # Block path escape
        if '..' in safe or safe.startswith('/'):
            return self._send_json(400, {'error': 'bad path'})
        full = os.path.join(ROOT, safe)
        if not os.path.isfile(full):
            return self._send_json(404, {'error': 'not found', 'path': rel_path})
        ext = os.path.splitext(full)[1].lower()
        mime = MIME.get(ext, 'application/octet-stream')
        size = os.path.getsize(full)
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        with open(full, 'rb') as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    # ── OPTIONS (CORS preflight) ──────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    # ── GET ────────────────────────────────────────────────────────
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        qs = parse_qs(url.query)

        # --- static routes ---
        if path in ('/', '/mobile', '/index.html'):
            return self._serve_static('mobile-demo.html')
        if path == '/mobile-demo.html':
            return self._serve_static('mobile-demo.html')
        if path in ('/dashboard', '/dashboard.html'):
            return self._serve_static('dashboard.html')
        if path.endswith(('.mp4', '.jpg', '.jpeg', '.png', '.svg', '.css', '.js', '.ico')):
            return self._serve_static(path)

        # --- admin: event stream ---
        if path == '/api/admin/events':
            since = int(qs.get('since', ['0'])[0])
            limit = max(1, min(500, int(qs.get('limit', ['200'])[0])))
            with connect() as conn:
                rows = conn.execute(
                    'SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT ?',
                    (since, limit)
                ).fetchall()
                total = conn.execute('SELECT COUNT(*) c FROM events').fetchone()['c']
                last_id = conn.execute('SELECT COALESCE(MAX(id), 0) m FROM events').fetchone()['m']
            return self._send_json(200, {
                'events':     [self._row_to_event(r) for r in rows],
                'total':      total,
                'last_id':    last_id,
                'killswitch': KILLSWITCH,
            })

        # --- admin: aggregated metrics ---
        if path == '/api/admin/metrics':
            return self._send_json(200, self._compute_metrics())

        # --- templates (dashboard editor + demo boot fetch) ---
        if path == '/api/templates':
            with connect() as conn:
                rows = conn.execute('SELECT key, content, default_content, updated_at FROM templates ORDER BY key').fetchall()
            return self._send_json(200, {
                'templates': {r['key']: dict(r) for r in rows},
                'meta':      TEMPLATE_META,
            })

        # --- sessions list for dashboard sidebar ---
        if path == '/api/admin/sessions':
            with connect() as conn:
                rows = conn.execute('''
                    SELECT
                      ai_session_id,
                      COUNT(DISTINCT violation_id) AS violations,
                      COUNT(*)                     AS events,
                      MAX(ts)                      AS last_ts
                    FROM events
                    WHERE ai_session_id IS NOT NULL
                    GROUP BY ai_session_id
                    ORDER BY last_ts DESC
                ''').fetchall()
            return self._send_json(200, {'sessions': [dict(r) for r in rows]})

        # --- session detail (used to drill into a session on the dashboard) ---
        if path.startswith('/api/sessions/') and path.count('/') == 3:
            sid = path.split('/')[-1]
            with connect() as conn:
                rows = conn.execute(
                    'SELECT * FROM events WHERE ai_session_id = ? ORDER BY id',
                    (sid,)
                ).fetchall()
            return self._send_json(200, {
                'ai_session_id': sid,
                'events':        [self._row_to_event(r) for r in rows],
            })

        return self._send_json(404, {'error': 'not found', 'path': path})

    # ── POST ───────────────────────────────────────────────────────
    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        data = self._read_json()

        # --- admin controls ---
        if path == '/api/admin/killswitch':
            KILLSWITCH['active'] = bool(data.get('active'))
            KILLSWITCH['reason'] = str(data.get('reason', '') or '')[:240]
            log_event('killswitch.toggle', payload={'active': KILLSWITCH['active'], 'reason': KILLSWITCH['reason']})
            return self._send_json(200, KILLSWITCH)

        if path == '/api/admin/reset':
            with connect() as conn:
                conn.execute('DELETE FROM events')
                conn.commit()
            KILLSWITCH['active'] = False
            KILLSWITCH['reason'] = ''
            return self._send_json(200, {'ok': True})

        # --- template edits (dashboard Templates tab) ---
        # POST /api/templates/{key}           → upsert content
        # POST /api/templates/{key}/reset     → reset one to default
        # POST /api/templates/reset-all       → reset everything
        if path.startswith('/api/templates'):
            parts = path.split('/')
            # /api/templates/reset-all
            if len(parts) == 4 and parts[3] == 'reset-all':
                with connect() as conn:
                    conn.execute('UPDATE templates SET content = default_content, updated_at = ?', (time.time(),))
                    conn.commit()
                log_event('template.reset_all', payload={'count': len(TEMPLATE_SEEDS)})
                return self._send_json(200, {'ok': True, 'reset': len(TEMPLATE_SEEDS)})
            # /api/templates/{key}/reset
            if len(parts) == 5 and parts[4] == 'reset':
                key = parts[3]
                with connect() as conn:
                    row = conn.execute('SELECT default_content FROM templates WHERE key = ?', (key,)).fetchone()
                    if not row:
                        return self._send_json(404, {'error': 'unknown key'})
                    conn.execute('UPDATE templates SET content = default_content, updated_at = ? WHERE key = ?', (time.time(), key))
                    conn.commit()
                    r2 = conn.execute('SELECT * FROM templates WHERE key = ?', (key,)).fetchone()
                log_event('template.reset', payload={'key': key})
                return self._send_json(200, {'ok': True, 'template': dict(r2)})
            # /api/templates/{key} — upsert content
            if len(parts) == 4:
                key = parts[3]
                content = str(data.get('content', ''))
                with connect() as conn:
                    exists = conn.execute('SELECT 1 FROM templates WHERE key = ?', (key,)).fetchone()
                    if not exists:
                        return self._send_json(404, {'error': 'unknown key', 'key': key})
                    conn.execute('UPDATE templates SET content = ?, updated_at = ? WHERE key = ?', (content, time.time(), key))
                    conn.commit()
                    r2 = conn.execute('SELECT * FROM templates WHERE key = ?', (key,)).fetchone()
                log_event('template.update', payload={'key': key, 'len': len(content)})
                return self._send_json(200, {'ok': True, 'template': dict(r2)})

        # --- session lifecycle: open ---
        parts = path.split('/')
        if len(parts) >= 5 and parts[1] == 'api' and parts[2] == 'sessions':
            sid = parts[3]
            action = parts[4]

            if action == 'open':
                log_event('session.open', ai_session_id=sid, violation_id=data.get('violation_id'), payload=data)
                if KILLSWITCH['active']:
                    return self._send_json(503, {
                        'error':      'killswitch_active',
                        'reason':     KILLSWITCH['reason'] or 'Operations has paused AI Insight.',
                        'killswitch': KILLSWITCH,
                    })
                return self._send_json(200, self._context_for(sid) | {'killswitch': KILLSWITCH})

            if action == 'messages':
                log_event('message', ai_session_id=sid, violation_id=data.get('violation_id'), payload=data)
                return self._send_json(200, {'ok': True})

            if action == 'intents':
                log_event('intent', ai_session_id=sid, violation_id=data.get('violation_id'), payload=data)
                return self._send_json(200, {'ok': True})

            if action == 'feedback':
                log_event('feedback.layer2', ai_session_id=sid, violation_id=data.get('violation_id'), payload=data)
                return self._send_json(200, {'ok': True})

        # --- message-level feedback (Layer 1) ---
        if path == '/api/messages/feedback':
            log_event(
                'feedback.layer1',
                ai_session_id=data.get('ai_session_id'),
                violation_id=data.get('violation_id'),
                payload=data
            )
            return self._send_json(200, {'ok': True})

        return self._send_json(404, {'error': 'not found', 'path': path})

    # ── helpers that touch the DB ──────────────────────────────────
    def _row_to_event(self, row):
        e = dict(row)
        try:
            e['payload'] = json.loads(e['payload'] or '{}')
        except Exception:
            e['payload'] = {}
        return e

    def _context_for(self, sid):
        """Mimics PRD §3.4 — return sibling-aware context for an ai_session."""
        with connect() as conn:
            touched = conn.execute(
                '''SELECT DISTINCT violation_id, MIN(id) AS first_id FROM events
                   WHERE ai_session_id = ? AND violation_id IS NOT NULL AND kind = 'session.open'
                   GROUP BY violation_id
                   ORDER BY first_id''',
                (sid,)
            ).fetchall()
            intents = conn.execute(
                "SELECT violation_id, payload FROM events WHERE ai_session_id = ? AND kind = 'intent' ORDER BY id",
                (sid,)
            ).fetchall()

        intents_by_v = {}
        for r in intents:
            try:
                p = json.loads(r['payload'] or '{}')
            except Exception:
                p = {}
            intents_by_v.setdefault(r['violation_id'], []).append(p.get('intent'))

        return {
            'ai_session_id':       sid,
            'violations_touched':  [r['violation_id'] for r in touched],
            'intents_by_violation': intents_by_v,
        }

    def _compute_metrics(self):
        with connect() as conn:
            counts = conn.execute('SELECT kind, COUNT(*) c FROM events GROUP BY kind').fetchall()
            l1 = conn.execute("SELECT payload FROM events WHERE kind = 'feedback.layer1'").fetchall()
            l2 = conn.execute("SELECT payload FROM events WHERE kind = 'feedback.layer2'").fetchall()
            intents = conn.execute("SELECT payload FROM events WHERE kind = 'intent'").fetchall()

        def safe(r):
            try: return json.loads(r['payload'] or '{}')
            except Exception: return {}

        l1_up   = sum(1 for r in l1 if safe(r).get('direction') == 'up')
        l1_down = sum(1 for r in l1 if safe(r).get('direction') == 'down')
        l2_help = sum(1 for r in l2 if safe(r).get('choice') == 'helpful')
        l2_unh  = sum(1 for r in l2 if safe(r).get('choice') == 'unhelpful')
        l2_skip = sum(1 for r in l2 if safe(r).get('choice') == 'skip')

        intent_dist = {}
        for r in intents:
            k = safe(r).get('intent') or 'unknown'
            intent_dist[k] = intent_dist.get(k, 0) + 1

        total_l1 = l1_up + l1_down
        return {
            'counts': {r['kind']: r['c'] for r in counts},
            'layer1': {
                'up': l1_up, 'down': l1_down,
                'pct_up': (l1_up / total_l1) if total_l1 else 0,
            },
            'layer2': {'helpful': l2_help, 'unhelpful': l2_unh, 'skip': l2_skip},
            'intents': intent_dist,
            'killswitch': KILLSWITCH,
        }


def main():
    init_db()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    banner = (
        f"\n🤖 TikTok LIVE · AI Insight mock backend\n"
        f"   Mobile demo  →  http://localhost:{PORT}/\n"
        f"   Ops dashboard →  http://localhost:{PORT}/dashboard\n"
        f"   SQLite        →  {DB_PATH}\n"
    )
    print(banner, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('shutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
