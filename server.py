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
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

# ──────────────────────────────────────────────────────────────────
# Claude Sonnet LLM — real inference via Anthropic API (stdlib only, no SDK).
# If ANTHROPIC_API_KEY isn't set, /api/chat/complete returns 503 and the
# frontend falls back to the hardcoded POLICY_* templates.
# ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
CLAUDE_MODEL      = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-6')
CLAUDE_API_URL    = 'https://api.anthropic.com/v1/messages'

# Evidence-submission (task 1.4) · confidence threshold to route to "priority reviewer".
# Conservative default — only ~15-20% of submissions clear the bar, minimising
# AI-vs-reviewer disagreement risk. Ops-tunable via env var without code change.
try:
    EVIDENCE_CONFIDENCE_THRESHOLD = float(os.environ.get('EVIDENCE_CONFIDENCE_THRESHOLD', '0.85'))
except Exception:
    EVIDENCE_CONFIDENCE_THRESHOLD = 0.85


def call_claude(system_prompt, messages, max_tokens=500):
    """Call Anthropic Messages API. Returns (text, meta) — text is None on failure."""
    if not ANTHROPIC_API_KEY:
        return None, {'error': 'no_api_key', 'hint': 'set ANTHROPIC_API_KEY env var'}
    body = {
        'model':      CLAUDE_MODEL,
        'max_tokens': max_tokens,
        'system':     system_prompt,
        'messages':   messages,
    }
    try:
        req = urllib.request.Request(
            CLAUDE_API_URL,
            data=json.dumps(body).encode('utf-8'),
            headers={
                'x-api-key':         ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
        parts = data.get('content', [])
        text  = ''.join(p.get('text', '') for p in parts if p.get('type') == 'text').strip()
        return text, {
            'model':       data.get('model'),
            'usage':       data.get('usage'),
            'stop_reason': data.get('stop_reason'),
        }
    except urllib.error.HTTPError as e:
        try:    body = json.loads(e.read().decode('utf-8'))
        except: body = {}
        return None, {'error': 'http_error', 'code': e.code, 'body': body}
    except Exception as e:
        return None, {'error': 'exception', 'message': str(e)}


def _build_llm_system_prompt(ctx):
    """Compose the system prompt from caller context. Grounded in PRD §2.1/§3 rules."""
    name       = ctx.get('user_name')        or 'Creator'
    level      = ctx.get('user_level')       or '?'
    archetype  = ctx.get('archetype')        or 'regular'
    prior      = ctx.get('prior_violations') or 0
    appeal_hx  = ctx.get('appeal_history')   or '(none)'
    vio_type   = ctx.get('violation_type')   or 'unknown'
    video_ts   = ctx.get('video_ts')         or 'unknown'
    policy     = (ctx.get('policy_description') or '').strip() or '(no policy text provided)'
    siblings   = ctx.get('sibling_intents')  or []
    return f"""You are the TikTok LIVE "AI Insight" assistant. Your job is to help creators
understand why their LIVE stream was flagged and what to do next — grounded in the
Community Guidelines policy text below.

OUTPUT RULES (strict):
- Total reply ≤280 characters (visual-equivalent of 140 Chinese characters, PRD §2.1 Scenario 3).
- Stay grounded in the provided policy — do not invent new rules, timestamps, or numbers.
- Never write the creator's appeal statement for them (PRD §2.1 Scenario 5).
- Only HTML allowed: <strong>, <em>, <br>. No other tags.
- Match tone to creator ARCHETYPE (see below).

CREATOR:
- Name: {name}
- Level: G{level} (archetype: {archetype})
- Prior {vio_type} flags in last 30 days: {prior}
- Appeal history: {appeal_hx}

ARCHETYPE TONE GUIDE:
- rookie     → warm · patient · explain the basics step-by-step · assume no prior knowledge
- regular    → balanced · direct · nothing unusual
- repeat     → firm but educational · explicitly reference pattern across flags
- premium    → concise · respectful · mention human specialist option when truly useful
- appealer   → acknowledge appeal history · careful language · keep appeal path visible but don't push

CURRENT VIOLATION:
- Type: {vio_type}
- Timestamp inside LIVE: {video_ts}

AI SESSION AGGREGATION (PRD §2.2):
On other same-type flags in this same LIVE, the creator previously picked these intents: {siblings or "(none)"}
You may reference this when helpful (e.g., "Earlier you asked about X — here's the follow-up for this segment.").

POLICY TEXT (ground truth):
\"\"\"{policy}\"\"\""""


INTENT_TO_USER_Q = {
    'understand': 'Why was my LIVE flagged?',
    'improve':    'How do I avoid this next time?',
    'nextSteps':  'What happens now?',
    'disagree':   "I don't think this flag is right.",
}


def preliminary_evidence_check(context_text, violation_type, ts):
    """Rate submitted creator context on a 0-1 'substantive' scale.

    With ANTHROPIC_API_KEY set, ask Claude to produce a numeric confidence.
    Without a key, use a deterministic heuristic so the demo still works.
    Never states "you were right" — just rates how substantive the evidence looks.
    """
    if ANTHROPIC_API_KEY:
        system = (
            "You are a moderation-triage assistant. Given a creator's submitted "
            "context/evidence about a flagged LIVE segment, rate on a scale 0.0-1.0 "
            "how substantive that context is — i.e. how likely it would change a "
            "human reviewer's decision. DO NOT judge whether the original flag was "
            "correct; only rate substantiveness.\n\n"
            "Respond with a single line JSON exactly: {\"confidence\": <float 0-1>, \"reason\": \"<≤20 words>\"}"
        )
        user = (
            f"violation_type: {violation_type}\n"
            f"flagged timestamp: {ts}\n"
            f"creator's context:\n{context_text}"
        )
        text, _meta = call_claude(system, [{'role': 'user', 'content': user}], max_tokens=120)
        if text:
            try:
                obj = json.loads(text.strip().split('\n')[0])
                c = float(obj.get('confidence', 0))
                return max(0.0, min(1.0, c)), obj.get('reason')
            except Exception:
                pass
    # Deterministic fallback — longer + more specific + timestamp-referenced
    # text trends more "substantive". Simulates what the classifier would surface.
    L = len(context_text or '')
    specificity = sum(1 for kw in ('at ', ':', 'because', 'actually', 'context',
                                   'intent', 'setup', 'cultural', 'satire', 'perform',
                                   'was', 'not', "wasn't") if kw in context_text.lower())
    length_score = min(1.0, L / 400.0)              # 0..1
    spec_score   = min(1.0, specificity / 8.0)      # 0..1
    score = 0.55 * length_score + 0.45 * spec_score
    return round(score, 3), 'length+specificity heuristic'

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
        # One-shot migration: fold URL-encoded ai_session_id values (containing %3A)
        # back into their canonical form so the inspector doesn't double-count sessions.
        n = conn.execute(
            "UPDATE events SET ai_session_id = REPLACE(ai_session_id, '%3A', ':') "
            "WHERE ai_session_id LIKE '%\\%3A%' ESCAPE '\\'"
        ).rowcount
        if n:
            print(f'[migrate] normalized {n} ai_session_id rows (%3A → :)', flush=True)
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

        # --- LLM status (dashboard or demo can show a connection indicator) ---
        if path == '/api/admin/llm-status':
            return self._send_json(200, {
                'available': bool(ANTHROPIC_API_KEY),
                'model':     CLAUDE_MODEL,
                'reason':    None if ANTHROPIC_API_KEY else 'ANTHROPIC_API_KEY not set',
            })

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
            sid = unquote(path.split('/')[-1])
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
            sid    = unquote(parts[3])
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

        # --- Claude-backed chat completion (falls back to templates if key missing) ---
        if path == '/api/chat/complete':
            ctx       = data.get('context') or {}
            intent    = data.get('intent')
            user_text = (data.get('text') or '').strip()

            system_prompt = _build_llm_system_prompt(ctx)

            # History → Anthropic message format (alternating user/assistant, first must be user)
            history   = ctx.get('history') or []
            messages  = []
            for m in history[-12:]:  # cap to last 12 turns
                role   = 'assistant' if (m.get('role') in ('ai', 'assistant')) else 'user'
                text   = (m.get('text') or '').strip()[:900]
                if text: messages.append({'role': role, 'content': text})
            # New turn — intent becomes a natural user question
            user_content = user_text or INTENT_TO_USER_Q.get(intent, 'Tell me more.')
            # Anthropic API requires the first message to be user + alternation. If history
            # ended on 'user' we drop the trailing one so the new user turn isn't back-to-back.
            while messages and messages[-1]['role'] == 'user':
                messages.pop()
            messages.append({'role': 'user', 'content': user_content})

            text, meta = call_claude(system_prompt, messages, max_tokens=500)

            log_event(
                'llm.request',
                ai_session_id=ctx.get('ai_session_id'),
                violation_id=ctx.get('violation_id'),
                payload={
                    'intent':            intent,
                    'user_text':         user_text[:200],
                    'archetype':         ctx.get('archetype'),
                    'user_level':        ctx.get('user_level'),
                    'success':           bool(text),
                    'model':             (meta or {}).get('model') if text else None,
                    'usage':             (meta or {}).get('usage') if text else None,
                    'error':             (meta or {}).get('error') if not text else None,
                    'response_preview':  (text or '')[:160],
                },
            )
            if text:
                return self._send_json(200, {
                    'reply':  text,
                    'model':  (meta or {}).get('model') or CLAUDE_MODEL,
                    'source': 'claude',
                    'usage':  (meta or {}).get('usage'),
                })
            return self._send_json(503, {
                'error':  'llm_unavailable',
                'source': 'fallback',
                'info':   meta,
            })

        # --- evidence submission (task 1.4) · high-threshold 2nd-look channel ---
        if path == '/api/evidence/submit':
            vid      = data.get('violation_id')
            sid      = data.get('ai_session_id')
            vtype    = data.get('violation_type') or 'unknown'
            ts       = (data.get('timestamp') or '').strip()
            context  = (data.get('context') or '').strip()
            if len(context) < 20:
                return self._send_json(400, {'error': 'context_too_short', 'min': 20})
            # Spam guard — one evidence submission per violation_id
            with connect() as conn:
                dup = conn.execute(
                    "SELECT 1 FROM events WHERE violation_id = ? AND kind = 'evidence.submitted' LIMIT 1",
                    (vid,)
                ).fetchone()
            if dup:
                return self._send_json(409, {'error': 'already_submitted', 'violation_id': vid})

            log_event('evidence.submitted', ai_session_id=sid, violation_id=vid, payload={
                'violation_type': vtype,
                'timestamp': ts,
                'context_length': len(context),
                'user_id':    data.get('user_id'),
                'user_level': data.get('user_level'),
                'archetype':  data.get('archetype'),
            })

            # Preliminary AI rating — threshold gate
            confidence, reason = preliminary_evidence_check(context, vtype, ts)
            positive = confidence >= EVIDENCE_CONFIDENCE_THRESHOLD

            kind = 'evidence.preliminary_positive' if positive else 'evidence.preliminary_neutral'
            reply = (
                'This evidence looks substantive. I\'ve tagged it for priority reviewer attention — '
                'you\'ll hear back within 24 h.'
                if positive else
                'Thanks — I\'ve logged your context with your appeal. The reviewer will weigh it.'
            )
            log_event(kind, ai_session_id=sid, violation_id=vid, payload={
                'confidence':   confidence,
                'threshold':    EVIDENCE_CONFIDENCE_THRESHOLD,
                'reason':       reason,
                'preview':      context[:120],
                'user_level':   data.get('user_level'),
                'archetype':    data.get('archetype'),
            })
            return self._send_json(200, {
                'preliminary': 'positive' if positive else 'neutral',
                'confidence':  confidence,
                'threshold':   EVIDENCE_CONFIDENCE_THRESHOLD,
                'reason':      reason,
                'reply':       reply,
                'source':      'claude' if ANTHROPIC_API_KEY else 'heuristic',
            })

        # --- demo · simulate a reviewer's final decision on a submitted evidence bundle ---
        if path == '/api/evidence/simulate-reviewer':
            vid    = data.get('violation_id')
            # If not provided, pick a random submitted-evidence violation
            with connect() as conn:
                if not vid:
                    row = conn.execute(
                        "SELECT violation_id FROM events WHERE kind = 'evidence.submitted' "
                        "AND violation_id NOT IN (SELECT violation_id FROM events WHERE kind = 'reviewer.final_decision') "
                        "ORDER BY RANDOM() LIMIT 1"
                    ).fetchone()
                    vid = row['violation_id'] if row else None
                if not vid:
                    return self._send_json(404, {'error': 'no_pending_evidence'})
                # Was the preliminary positive or neutral?
                prelim = conn.execute(
                    "SELECT kind FROM events WHERE violation_id = ? AND kind LIKE 'evidence.preliminary_%' LIMIT 1",
                    (vid,)
                ).fetchone()
            preliminary_was_positive = (prelim and prelim['kind'] == 'evidence.preliminary_positive')
            # Deterministic-ish simulation: reviewers agree with AI ~75 % of the time.
            import random
            agreed = random.random() < 0.75
            decision = ('approved' if preliminary_was_positive else 'denied') if agreed else \
                       ('denied'   if preliminary_was_positive else 'approved')
            log_event('reviewer.final_decision', violation_id=vid, payload={
                'decision':             decision,
                'preliminary_positive': bool(preliminary_was_positive),
                'agreed_with_ai':       agreed,
            })
            return self._send_json(200, {
                'violation_id': vid, 'decision': decision,
                'preliminary_positive': bool(preliminary_was_positive),
                'agreed_with_ai': agreed,
            })

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
            # Tier distribution — one entry per distinct (user_id|violation_id) opened
            opens = conn.execute("SELECT payload FROM events WHERE kind = 'session.open'").fetchall()
            # Human-agent queue events (role=system · event=human_agent_queued · or from mobile beacon)
            all_msgs = conn.execute("SELECT payload FROM events WHERE kind = 'message'").fetchall()
            # Track-C restriction feedback (§1.1) — carried inside feedback.layer1 with surface=restriction
            # Evidence submissions + reviewer decisions (§1.4)
            ev_pos  = conn.execute("SELECT COUNT(*) c FROM events WHERE kind = 'evidence.preliminary_positive'").fetchone()['c']
            ev_neu  = conn.execute("SELECT COUNT(*) c FROM events WHERE kind = 'evidence.preliminary_neutral'").fetchone()['c']
            ev_sub  = conn.execute("SELECT COUNT(*) c FROM events WHERE kind = 'evidence.submitted'").fetchone()['c']
            rv_dec  = conn.execute("SELECT payload FROM events WHERE kind = 'reviewer.final_decision'").fetchall()

        def safe(r):
            try: return json.loads(r['payload'] or '{}')
            except Exception: return {}

        # Track AB — message-level (chat quality). Exclude restriction-surface entries.
        l1_up   = sum(1 for r in l1 if safe(r).get('direction') == 'up'   and safe(r).get('surface') != 'restriction')
        l1_down = sum(1 for r in l1 if safe(r).get('direction') == 'down' and safe(r).get('surface') != 'restriction')
        # Track C — restriction-agreement (civic feedback, task 1.1) carried on the same endpoint.
        restrict_agree    = sum(1 for r in l1 if safe(r).get('surface') == 'restriction' and safe(r).get('choice') == 'agree')
        restrict_disagree = sum(1 for r in l1 if safe(r).get('surface') == 'restriction' and safe(r).get('choice') == 'disagree')
        # Layer 2 · split explicit vs auto-derived (task 1.2)
        l2_help_exp  = sum(1 for r in l2 if safe(r).get('choice') == 'helpful'   and not safe(r).get('auto_derived'))
        l2_help_auto = sum(1 for r in l2 if safe(r).get('choice') == 'helpful'   and safe(r).get('auto_derived'))
        l2_unh_exp   = sum(1 for r in l2 if safe(r).get('choice') == 'unhelpful' and not safe(r).get('auto_derived'))
        l2_unh_auto  = sum(1 for r in l2 if safe(r).get('choice') == 'unhelpful' and safe(r).get('auto_derived'))
        l2_skip      = sum(1 for r in l2 if safe(r).get('choice') == 'skip')
        l2_help = l2_help_exp + l2_help_auto
        l2_unh  = l2_unh_exp  + l2_unh_auto

        intent_dist = {}
        for r in intents:
            k = safe(r).get('intent') or 'unknown'
            intent_dist[k] = intent_dist.get(k, 0) + 1

        # Tier (G1-G11) distribution from session.open events. Dedupe by (user_id, violation_id)
        # so one user browsing multiple times doesn't double-count their tier.
        seen = set()
        tiers = {}
        for r in opens:
            p = safe(r)
            key = (p.get('user_id') or '-', p.get('violation_id') or '-')
            if key in seen:
                continue
            seen.add(key)
            lvl = p.get('user_level')
            if not lvl:
                continue
            tiers['G' + str(lvl)] = tiers.get('G' + str(lvl), 0) + 1

        human_queued = sum(1 for r in all_msgs if safe(r).get('event') == 'human_agent_queued')

        total_l1 = l1_up + l1_down

        # Task 1.4 · AI vs reviewer agreement rate
        agree_n = 0
        rev_total = 0
        for r in rv_dec:
            p = safe(r)
            rev_total += 1
            if p.get('agreed_with_ai'):
                agree_n += 1
        agreement_rate = (agree_n / rev_total) if rev_total else None

        return {
            'counts': {r['kind']: r['c'] for r in counts},
            'layer1': {
                'up': l1_up, 'down': l1_down,
                'pct_up': (l1_up / total_l1) if total_l1 else 0,
            },
            'layer2': {
                'helpful': l2_help, 'unhelpful': l2_unh, 'skip': l2_skip,
                'explicit': {'helpful': l2_help_exp, 'unhelpful': l2_unh_exp},
                'auto':     {'helpful': l2_help_auto, 'unhelpful': l2_unh_auto},
            },
            'restriction_agreement': {
                'agree':    restrict_agree,
                'disagree': restrict_disagree,
                'pct_agree': (restrict_agree / (restrict_agree + restrict_disagree))
                              if (restrict_agree + restrict_disagree) else None,
            },
            'evidence': {
                'submitted':           ev_sub,
                'preliminary_positive': ev_pos,
                'preliminary_neutral':  ev_neu,
                'reviewer_decisions':   rev_total,
                'ai_reviewer_agreement_rate': agreement_rate,
                'threshold':           EVIDENCE_CONFIDENCE_THRESHOLD,
            },
            'intents': intent_dist,
            'tiers':   tiers,
            'human_agent_queued': human_queued,
            'llm':        {'available': bool(ANTHROPIC_API_KEY), 'model': CLAUDE_MODEL},
            'killswitch': KILLSWITCH,
        }


def main():
    init_db()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    llm_line = (
        f"   Claude LLM    →  ✓ {CLAUDE_MODEL} (ANTHROPIC_API_KEY set)"
        if ANTHROPIC_API_KEY else
        f"   Claude LLM    →  ✗ not configured · using template fallback "
        f"(set ANTHROPIC_API_KEY to enable Sonnet)"
    )
    banner = (
        f"\n🤖 TikTok LIVE · AI Insight mock backend\n"
        f"   Mobile demo  →  http://localhost:{PORT}/\n"
        f"   Ops dashboard →  http://localhost:{PORT}/dashboard\n"
        f"   SQLite        →  {DB_PATH}\n"
        f"{llm_line}\n"
    )
    print(banner, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('shutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
