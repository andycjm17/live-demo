# TikTok LIVE · AI Insight Demo

Mobile prototype + ops dashboard + mock backend for the AI Insight violation-education flow described in the [TikTok LIVE AI Insight PRD](TikTok_LIVE_AI_Insight_PRD.docx). Phase 1 MVP, Claude Sonnet-backed, single-file surfaces, iPhone-17 sized (402 × 874).

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/andycjm17/live-demo)

## One-click cloud share

Click the badge above → Render connects the repo → paste your `ANTHROPIC_API_KEY` when prompted → in ~2-3 min you have a public URL like `https://ai-insight-demo.onrender.com` to share. Everything is pre-declared in [render.yaml](render.yaml).

| Env var | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes for live Claude** · optional for template-only demo | Enables Sonnet-backed replies. Without it the demo falls back to the hardcoded policy templates (the `📋 Template fallback` badge shows under each AI bubble). |
| `CLAUDE_MODEL` | no (defaults to `claude-sonnet-4-6`) | Override model id if needed. |
| `EVIDENCE_CONFIDENCE_THRESHOLD` | no (defaults to `0.85`) | Cutoff for routing evidence submissions to the priority reviewer. |
| `PORT` | auto-injected by Render | Server binds here. |

Free-tier caveats: the service spins down after 15 min of inactivity (cold start ≈ 30 s on the next visit), and `aiinsight.db` is ephemeral — redeploy or cold-start wipes it. The dashboard's **🌱 Seed 100 mock conversations** button repopulates in ~6 s.

## Run locally

```bash
cd live-demo
export ANTHROPIC_API_KEY='sk-ant-...'    # optional — omit to run template-only
python3 server.py                         # serves demo + dashboard + API on :8765
```

Open:
- Mobile demo — http://localhost:8765/
- Ops dashboard — http://localhost:8765/dashboard

No `pip install` step — pure Python stdlib. `requirements.txt` is intentionally empty.

## Surfaces

| Path | What |
|---|---|
| `/` (or `/mobile`) | iPhone-sized mobile demo (`mobile-demo.html`) |
| `/dashboard` | Ops dashboard (`dashboard.html`) — live events / templates editor / AI aggregation inspector / kill switch |
| `/api/sessions/*` | Event beacons from the mobile demo |
| `/api/chat/complete` | Claude Sonnet-backed chat completion (falls back to templates if key missing) |
| `/api/admin/*` | Dashboard endpoints (events stream, metrics, kill switch, template store, reset) |

## Files

| File | Purpose |
|---|---|
| `mobile-demo.html` | Entire mobile demo — HTML + CSS + JS in one file, 5 creator archetypes, login → end-stream → restrictions flow |
| `dashboard.html` | Ops dashboard — live event stream, metrics, kill switch, response-template editor, AI aggregation inspector |
| `server.py` | Python-stdlib HTTP server + SQLite + Claude API client |
| `render.yaml` | Render.com deploy blueprint |
| `requirements.txt` | Empty · satisfies platform Python detectors |
| `clip-*.mp4` / `.jpg` | Violation clip assets (Inorganic Gift Solicitation + Body Exposure) |

## Demo account archetypes (login screen)

| Card | Level | Archetype | Showcases |
|---|---|---|---|
| 🌱 Rookie Sarah | G2 | rookie | Warm onboarding tone · first-flag framing |
| 🎤 Baseline Jay | G5 | regular | Reference UX journey (nothing special) |
| 🧢 Repeat-flagger Mike | G4 | repeat | "5th flag in 30d" inbox banner · aggregation-aware AI opener |
| 💎 VIP Zoe | G10 ⭐ | premium | Human-agent banner always visible in chat · priority-queue modal |
| ⚖️ Serial-appealer Alex | G7 | appealer | Appeal-history banner · AI acknowledges past disputes |

Each account has its own localStorage namespace — one creator's chat history never leaks into another's aggregation prefix.

## PRD UX patterns wired in

| PRD ref | Behaviour |
|---|---|
| §2.1 Scenario 1 | Per-violation push notifications · deep-link to the Violation Page |
| §2.1 Scenario 2 | Clip collapsed by default · 4 visually-equal intents · 200 ms pick-once fade · impact pill in hero · single "🗨️ Keep conversation" CTA when prior chat exists |
| §2.1 Scenario 3 | Typewriter at 25 ms/char · 16 px 👍/👎 embedded in bubble bottom-right, fade in only after typing completes · **first opener is instant (no typewriter)** |
| §2.1 Scenario 4 | Layer-2 session feedback bottom sheet — triggers on close when chat had ≥2 turns and Layer-1 has <3 same-direction votes |
| §2.1 Scenario 5 | Unified appeal modal · in-chat "File a formal appeal" funnels to the same option-pick modal · AI never drafts the appeal text |
| §2.2 | Multi-violation inbox (3 items under one `live_session`) grouped by session · AI session aggregation by (`live_session`, `violation_type`) · opener surfaces "This is your 2nd X flag — earlier we walked through Y." |
| §3.3 Layer 8 | Kill switch returns 503 on `session.open` · mobile demo renders yellow "AI Insight paused by operations" banner |
| §3.4 | Persistent conversation per (user, violation) via localStorage · "Keep conversation" restores prior messages instantly |
| §3.5 | 3-tier feedback pipeline logged to backend: Layer 1 message-level, Layer 2 session-level, Layer 3 behaviour (reserved) |

## "Is it really Claude?"

Each AI bubble shows a source tag: `✨ Claude Sonnet 4.6` when the response came from the Anthropic API, `📋 Template fallback` when it came from the hardcoded `POLICY_*` templates. The dashboard's `llm.request` event also logs token usage per call.

## Not a production system

UX-only prototype for design review and stakeholder walk-throughs. Real backend, RAG retrieval, attack-classifier, citation hard-match, persistent conversation storage etc. live in §3 of the PRD.
